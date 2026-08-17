from supabase import Client, create_client


def build_supabase_client(url: str, key: str) -> Client:
    """
    Creates the shared Supabase client. Wire it once at startup and
    inject it into every repository adapter that needs it.
    """
    return create_client(url, key)
