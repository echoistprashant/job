import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.browser.field_mapper import FieldMapper
from backend.app.browser.models import FormDiagnosticReport, FormFieldDiagnostic


class ScreeningQuestion(BaseModel):
    id: str
    prompt: str
    field_type: str = "text"  # "text", "textarea", "select", "radio", "checkbox"
    required: bool = False
    options: List[str] = Field(default_factory=list)
    selector: str
    category: str = "general"  # "experience", "motivation", "authorization", "compensation", "availability", "general"


class QuestionExtractor:
    """
    Phase 32: Extract and categorize open-ended and screening questions
    from form diagnostic reports, clearly separating standard candidate
    profile fields (e.g. name, email, phone) from custom employer questions.
    """

    QUESTION_KEYWORDS = [
        r"(?i)\bwhy\b",
        r"(?i)\bhow\s+(many|much|did|do)\b",
        r"(?i)\bdescribe\b",
        r"(?i)\bexplain\b",
        r"(?i)\btell\s+us\b",
        r"(?i)\bwhat\s+(is|are|experience|makes|interests)\b",
        r"(?i)\bdo\s+you\b",
        r"(?i)\bare\s+you\b",
        r"(?i)\bhave\s+you\b",
        r"(?i)\bwill\s+you\b",
        r"(?i)\bnotice\s+period\b",
        r"(?i)\bsalary\s+(expectation|requirement)\b",
        r"(?i)\bcompensation\b",
        r"(?i)\bauthorized\s+to\s+work\b",
        r"(?i)\bsponsorship\b",
        r"(?i)\byears\s+of\s+experience\b",
    ]

    CATEGORY_PATTERNS = {
        "authorization": [
            r"(?i)\bauthorized\b",
            r"(?i)\bwork\s+authorization\b",
            r"(?i)\bsponsorship\b",
            r"(?i)\bvisa\b",
            r"(?i)\blegally\b",
            r"(?i)\bcitizen\b",
        ],
        "motivation": [
            r"(?i)\bwhy\s+(do\s+you\s+want|are\s+you\s+interested)\b",
            r"(?i)\bwhat\s+(interests|excites)\s+you\b",
            r"(?i)\bcover\s+letter\b",
            r"(?i)\babout\s+yourself\b",
        ],
        "experience": [
            r"(?i)\bexperience\b",
            r"(?i)\bhow\s+many\s+years\b",
            r"(?i)\bdescribe\s+(a\s+time|a\s+project|your\s+experience)\b",
            r"(?i)\bproficiency\b",
            r"(?i)\bworked\s+with\b",
        ],
        "compensation": [
            r"(?i)\bsalary\b",
            r"(?i)\bcompensation\b",
            r"(?i)\brate\b",
            r"(?i)\bpay\b",
        ],
        "availability": [
            r"(?i)\bnotice\s+period\b",
            r"(?i)\bstart\s+date\b",
            r"(?i)\bwhen\s+can\s+you\s+start\b",
            r"(?i)\bavailable\b",
        ],
    }

    def __init__(self):
        self.field_mapper = FieldMapper()

    def is_standard_profile_field(self, field: FormFieldDiagnostic) -> bool:
        """Check if a field maps to standard candidate personal profile attributes."""
        std_field = self.field_mapper.identify_field_type(field)
        return std_field is not None

    def categorize_question(self, prompt: str) -> str:
        """Classify question into an operational category."""
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, prompt):
                    return category
        return "general"

    def is_question_like(self, field: FormFieldDiagnostic) -> bool:
        """Determine if an input is an open-ended or screening question."""
        if field.tag == "textarea":
            return True

        text_to_check = f"{field.label or ''} {field.placeholder or ''} {field.name or ''}"

        if "?" in text_to_check:
            return True

        for kw in self.QUESTION_KEYWORDS:
            if re.search(kw, text_to_check):
                return True

        if field.tag == "select" and field.options:
            if any(re.search(pat, text_to_check) for pats in self.CATEGORY_PATTERNS.values() for pat in pats):
                return True

        return False

    def extract_questions(self, report: FormDiagnosticReport) -> List[ScreeningQuestion]:
        """
        Extract and return all screening questions from a form diagnostic report,
        filtering out standard demographic profile inputs.
        """
        questions: List[ScreeningQuestion] = []
        all_candidates: List[FormFieldDiagnostic] = (
            report.inputs + report.selects + report.textareas
        )

        counter = 1
        for field in all_candidates:
            if field.field_type in ["hidden", "submit", "button", "reset", "file"]:
                continue

            if self.is_standard_profile_field(field):
                continue

            if self.is_question_like(field):
                prompt = (
                    field.label
                    or field.placeholder
                    or field.aria_label
                    or field.name
                    or f"Question {counter}"
                ).strip()

                prompt_clean = re.sub(r"\s*\*+$", "", prompt).strip()
                category = self.categorize_question(prompt_clean)
                q_id = field.name or field.id or f"q_{counter}"

                questions.append(
                    ScreeningQuestion(
                        id=q_id,
                        prompt=prompt_clean,
                        field_type=field.field_type if field.field_type != "text" else field.tag,
                        required=field.required,
                        options=field.options,
                        selector=field.selector,
                        category=category,
                    )
                )
                counter += 1

        return questions


question_extractor = QuestionExtractor()
