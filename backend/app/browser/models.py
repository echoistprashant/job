from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FormFieldDiagnostic(BaseModel):
    tag: str = Field(..., description="HTML tag: input, select, textarea, button")
    field_type: str = Field(default="text", description="Type attribute: text, email, tel, file, radio, checkbox, etc.")
    name: Optional[str] = None
    id: Optional[str] = None
    placeholder: Optional[str] = None
    label: Optional[str] = None
    aria_label: Optional[str] = None
    required: bool = False
    options: List[str] = Field(default_factory=list, description="Options if select dropdown or radio group")
    selector: str = Field(..., description="Playwright-compatible CSS or XPath selector")


class FormDiagnosticReport(BaseModel):
    url: str
    page_title: str
    total_fields: int
    inputs: List[FormFieldDiagnostic] = Field(default_factory=list)
    selects: List[FormFieldDiagnostic] = Field(default_factory=list)
    textareas: List[FormFieldDiagnostic] = Field(default_factory=list)
    file_inputs: List[FormFieldDiagnostic] = Field(default_factory=list)
    buttons: List[str] = Field(default_factory=list)


class PageNavigationResult(BaseModel):
    url: str
    final_url: str
    title: str
    status_code: int = 200
    load_time_ms: float = 0.0
    form_report: Optional[FormDiagnosticReport] = None
