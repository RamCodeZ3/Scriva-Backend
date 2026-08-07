from __future__ import annotations

import os
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from domain.entities.source import SourceType
from domain.entities.user import User

from application.ports.document_exporter_port import DocumentExporterPort
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.document_writer_port import DocumentWriterPort
from application.ports.extractor_factory_port import ExtractorFactoryPort
from application.ports.google_credentials_port import GoogleCredentialsPort
from application.ports.source_repository_port import SourceRepositoryPort
from application.ports.user_repository_port import UserRepositoryPort
from application.use_cases.create_document_use_case import CreateDocumentUseCase
from application.use_cases.process_document_use_case import ProcessDocumentUseCase

from infrastructure.ai.gemini_document_writer_adapter import GeminiDocumentWriterAdapter
from infrastructure.auth.google_oauth_token_provider import GoogleOAuthTokenProvider
from infrastructure.auth.supabase_jwt_auth import InvalidTokenError, SupabaseJWTAuth
from infrastructure.export.google_docs_exporter_adapter import GoogleDocsExporterAdapter
from infrastructure.extractors.extractor_factory_adapter import ExtractorFactoryAdapter
from infrastructure.extractors.file_extractor_adapter import FileExtractorAdapter
from infrastructure.extractors.text_extractor_adapter import PlainTextExtractorAdapter
from infrastructure.extractors.web_extractor_adapter import WebExtractorAdapter
from infrastructure.extractors.youtube_extractor_adapter import YoutubeExtractorAdapter
from infrastructure.jobs.sync_job_dispatcher_adapter import SyncJobDispatcherAdapter
from infrastructure.persistence.supabase_client import build_supabase_client
from infrastructure.persistence.supabase_document_repository import SupabaseDocumentRepository
from infrastructure.persistence.supabase_google_credentials_repository import (
    SupabaseGoogleCredentialsRepository,
)
from infrastructure.persistence.supabase_source_repository import SupabaseSourceRepository
from infrastructure.persistence.supabase_user_repository import SupabaseUserRepository


# ── Process-wide singletons ─────────────────────────────────────────────
# Built once and reused across requests — anything with its own
# connection pool / expensive init belongs here, not per-request.

@lru_cache
def get_supabase_client():
    return build_supabase_client(
        url=os.environ["SUPABASE_URL"],
        key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


@lru_cache
def get_jwt_auth() -> SupabaseJWTAuth:
    return SupabaseJWTAuth(jwt_secret=os.environ["SUPABASE_JWT_SECRET"])


@lru_cache
def get_extractor_factory() -> ExtractorFactoryPort:
    return ExtractorFactoryAdapter(
        {
            SourceType.WEB: WebExtractorAdapter(),
            SourceType.YOUTUBE: YoutubeExtractorAdapter(),
            SourceType.FILE: FileExtractorAdapter(),
            SourceType.TEXT: PlainTextExtractorAdapter(),
        }
    )


@lru_cache
def get_document_writer() -> DocumentWriterPort:
    return GeminiDocumentWriterAdapter(api_key=os.environ["GEMINI_API_KEY"])


@lru_cache
def get_google_credentials_repository() -> GoogleCredentialsPort:
    # Reads a table written by the *other* backend (Google OAuth
    # consent lives there). The encryption key must match theirs.
    return SupabaseGoogleCredentialsRepository(
        get_supabase_client(),
        encryption_key=os.environ["GOOGLE_TOKEN_ENCRYPTION_KEY"],
    )


@lru_cache
def get_google_oauth_token_provider() -> GoogleOAuthTokenProvider:
    return GoogleOAuthTokenProvider(
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
    )


# ── Repositories ─────────────────────────────────────────────────────────

def get_user_repository() -> UserRepositoryPort:
    return SupabaseUserRepository(get_supabase_client())


def get_source_repository() -> SourceRepositoryPort:
    return SupabaseSourceRepository(get_supabase_client())


def get_document_repository(
    source_repository: SourceRepositoryPort = Depends(get_source_repository),
) -> DocumentRepositoryPort:
    return SupabaseDocumentRepository(get_supabase_client(), source_repository)


# ── Auth ─────────────────────────────────────────────────────────────────
# Supabase Auth's user id and this service's business `users.id` are
# the same value now, so the JWT's `sub` claim IS the user id directly
# — no auth_id -> id lookup, no extra table.

async def get_current_user_id(
    authorization: str = Header(..., alias="Authorization"),
    jwt_auth: SupabaseJWTAuth = Depends(get_jwt_auth),
) -> UUID:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected: 'Bearer <token>'.",
        )

    try:
        payload = jwt_auth.decode(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}"
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no 'sub' claim."
        )

    try:
        return UUID(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 'sub' is not a valid UUID."
        ) from exc


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
) -> User:
    """
    Resolves the business `users` row for the authenticated account.
    Since this service doesn't manage user creation, a missing row
    means the account hasn't been provisioned yet by the other backend.
    """
    user = await user_repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not registered in the documents service yet.",
        )
    return user


# ── Google Docs export (per-user OAuth, stored refresh_token) ───────────
# The document is created directly in *the user's own* Google Drive.
# The refresh_token was obtained during the OAuth consent handled by
# the other backend and is only read here; we exchange it for a fresh
# access_token on every call, nothing long-lived is cached in memory.

async def get_google_access_token(
    current_user: User = Depends(get_current_user),
    credentials_repository: GoogleCredentialsPort = Depends(get_google_credentials_repository),
    token_provider: GoogleOAuthTokenProvider = Depends(get_google_oauth_token_provider),
) -> str:
    refresh_token = await credentials_repository.get_refresh_token(current_user.id)
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account hasn't granted Google Docs/Drive access yet.",
        )

    try:
        return await token_provider.get_access_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not refresh Google credentials: {exc}",
        ) from exc


def get_document_exporter(
    google_access_token: str = Depends(get_google_access_token),
) -> DocumentExporterPort:
    return GoogleDocsExporterAdapter(user_access_token=google_access_token)


# ── Use cases ────────────────────────────────────────────────────────────

def get_process_document_use_case(
    document_repository: DocumentRepositoryPort = Depends(get_document_repository),
    source_repository: SourceRepositoryPort = Depends(get_source_repository),
    extractor_factory: ExtractorFactoryPort = Depends(get_extractor_factory),
    document_writer: DocumentWriterPort = Depends(get_document_writer),
    document_exporter: DocumentExporterPort = Depends(get_document_exporter),
) -> ProcessDocumentUseCase:
    return ProcessDocumentUseCase(
        document_repository=document_repository,
        source_repository=source_repository,
        extractor_factory=extractor_factory,
        document_writer=document_writer,
        document_exporter=document_exporter,
    )


def get_create_document_use_case(
    document_repository: DocumentRepositoryPort = Depends(get_document_repository),
    source_repository: SourceRepositoryPort = Depends(get_source_repository),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
    process_use_case: ProcessDocumentUseCase = Depends(get_process_document_use_case),
) -> CreateDocumentUseCase:
    # Sync dispatcher: the whole pipeline runs before this endpoint
    # answers. See SyncJobDispatcherAdapter's docstring for the tradeoffs.
    dispatcher = SyncJobDispatcherAdapter(process_use_case)
    return CreateDocumentUseCase(
        document_repository=document_repository,
        source_repository=source_repository,
        user_repository=user_repository,
        job_dispatcher=dispatcher,
    )
