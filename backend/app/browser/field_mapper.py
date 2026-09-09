import re
from typing import Any, Dict, List, Optional, Tuple
from backend.app.browser.models import FormFieldDiagnostic
from backend.app.models.resume import CandidateProfile


class FieldMapper:
    """
    Semantic field mapping layer that connects detected accessible form attributes
    (names, labels, IDs, placeholders) to candidate profile values without screen coordinates.
    """

    PATTERNS = {
        "first_name": [
            r"(?i)\bfirst[_\-\s]?name\b",
            r"(?i)\bgiven[_\-\s]?name\b",
            r"(?i)\bfname\b"
        ],
        "last_name": [
            r"(?i)\blast[_\-\s]?name\b",
            r"(?i)\bsurname\b",
            r"(?i)\bfamily[_\-\s]?name\b",
            r"(?i)\blname\b"
        ],
        "full_name": [
            r"(?i)\bfull[_\-\s]?name\b",
            r"(?i)\byour[_\-\s]?name\b",
            r"(?i)^name$"
        ],
        "email": [
            r"(?i)\bemail\b",
            r"(?i)\be-mail\b",
            r"(?i)\buser_email\b"
        ],
        "phone": [
            r"(?i)\bphone\b",
            r"(?i)\bmobile\b",
            r"(?i)\btel\b",
            r"(?i)\btelephone\b",
            r"(?i)\bcontact[_\-\s]?number\b"
        ],
        "linkedin": [
            r"(?i)\blinkedin\b",
            r"(?i)\blinked_in\b"
        ],
        "github": [
            r"(?i)\bgithub\b",
            r"(?i)\bgit\b"
        ],
        "website": [
            r"(?i)\bwebsite\b",
            r"(?i)\bportfolio\b",
            r"(?i)\bpersonal[_\-\s]?site\b"
        ],
        "location": [
            r"(?i)\blocation\b",
            r"(?i)\bcity\b",
            r"(?i)\baddress\b"
        ],
        "resume": [
            r"(?i)\bresume\b",
            r"(?i)\bcv\b",
            r"(?i)\bcurriculum[_\-\s]?vitae\b"
        ]
    }

    def identify_field_type(self, field: FormFieldDiagnostic) -> Optional[str]:
        """Identify standard semantic field key based on attributes and surrounding label text."""
        # 1. If file input, check if it's for resume
        if field.field_type == "file":
            return "resume"

        # Check HTML5 native input types
        if field.field_type == "email":
            return "email"
        if field.field_type == "tel":
            return "phone"

        # Test against composite text attribute
        composite = f"{field.name or ''} {field.id or ''} {field.label or ''} {field.placeholder or ''} {field.aria_label or ''}"

        for field_key, regex_list in self.PATTERNS.items():
            for pat in regex_list:
                if re.search(pat, composite):
                    return field_key

        return None

    def get_candidate_value(self, field_type: str, profile: CandidateProfile) -> Optional[str]:
        """Map semantic field key to known candidate profile attribute."""
        cand = profile.candidate
        name_parts = (cand.name or "Candidate").split(maxsplit=1)
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        mapping: Dict[str, Optional[str]] = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": cand.name,
            "email": cand.email,
            "phone": cand.phone,
            "linkedin": cand.linkedin,
            "github": cand.github,
            "website": cand.github or cand.linkedin,
            "location": cand.location or (profile.locations[0] if profile.locations else "Remote")
        }
        return mapping.get(field_type)

    def resolve_select_option(
        self,
        field: FormFieldDiagnostic,
        profile: CandidateProfile
    ) -> Tuple[Optional[str], bool]:
        """
        Safely match a select dropdown option without guessing.
        Returns (selected_option, is_ambiguous).
        """
        composite = f"{field.name or ''} {field.id or ''} {field.label or ''}".lower()
        options = field.options

        # Experience dropdown
        if "experience" in composite or "exp" in composite:
            cand_level = profile.experience_level.lower()
            for opt in options:
                opt_lower = opt.lower()
                if "entry" in cand_level or "0-2" in cand_level:
                    if "0-1" in opt_lower or "0-2" in opt_lower or "entry" in opt_lower or "junior" in opt_lower:
                        return opt, False
                elif "mid" in cand_level:
                    if "2-4" in opt_lower or "3-5" in opt_lower or "mid" in opt_lower:
                        return opt, False
                elif "senior" in cand_level:
                    if "5+" in opt_lower or "senior" in opt_lower:
                        return opt, False

        # Work authorization dropdown
        if "authorized" in composite or "sponsorship" in composite:
            # Conservative: if options contain Clear Yes/No, flag as ambiguous if not explicitly stated in profile
            return None, True

        # If choice cannot be determined with certainty, flag ambiguous instead of guessing
        return None, True


field_mapper = FieldMapper()
