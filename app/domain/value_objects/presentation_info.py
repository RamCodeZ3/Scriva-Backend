from dataclasses import dataclass


@dataclass(frozen=True)
class PresentationInfo:
    """
    Metadata shown on the document cover page (APA 7 title page).
    Only student_name, professor and subject are required.
    """

    student_name: str
    professor: str
    subject: str
    student_id: str | None = None  # optional: student ID / matricula
    institution: str | None = None  # optional: university or institute

    def __post_init__(self) -> None:
        if not self.student_name.strip():
            raise ValueError("student_name cannot be empty.")
        if not self.professor.strip():
            raise ValueError("professor cannot be empty.")
        if not self.subject.strip():
            raise ValueError("subject cannot be empty.")

    def display_institution(self) -> str:
        return self.institution or "Institution not specified"

    def display_student_id(self) -> str:
        return self.student_id or "N/A"
