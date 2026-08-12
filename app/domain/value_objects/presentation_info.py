from dataclasses import dataclass


@dataclass(frozen=True)
class PresentationInfo:
    """
    Metadata shown on the document cover page (APA 7 title page).
    Only student_name and professor are required; subject is optional.
    """

    student_name: str
    professor: str
    subject: str | None = None
    student_id: str | None = None
    institution: str | None = None

    def __post_init__(self) -> None:
        if not self.student_name.strip():
            raise ValueError("student_name cannot be empty.")
        if not self.professor.strip():
            raise ValueError("professor cannot be empty.")
        if self.subject is not None and not self.subject.strip():
            raise ValueError("subject cannot be blank if provided.")

    def display_institution(self) -> str:
        return self.institution or "Institution not specified"

    def display_student_id(self) -> str:
        return self.student_id or "N/A"

    def display_subject(self) -> str:
        return self.subject or "Subject not specified"
