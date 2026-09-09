import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import Page

from backend.app.browser.browser import browser_service
from backend.app.browser.field_mapper import field_mapper
from backend.app.models.application import ApplicationDraftResult
from backend.app.models.job import Job
from backend.app.models.resume import CandidateProfile

logger = logging.getLogger("ai_job_agent.application_agent")


class ApplicationAgent:
    """
    Automates job application forms using Playwright:
    1. Inspects form controls semantically.
    2. Fills known candidate profile fields.
    3. Handles resume attachments with DOM verification.
    4. Handles selects/checkboxes safely, flagging ambiguous choices.
    5. STRICTLY STOPS before submission to produce an application draft.
    """

    async def prepare_application_draft(
        self,
        job: Job,
        profile: CandidateProfile,
        resume_file_path: Optional[str] = None
    ) -> ApplicationDraftResult:
        """
        Open job application URL, fill known fields, attach resume, and stop before submission.
        """
        # 1. Open page in isolated context
        page, context, nav_result, own_context = await browser_service.open_page(job.url)

        try:
            # 2. Inspect page structure
            report = await browser_service.inspect_page_structure(page)
            browser_service.save_diagnostic_report(report)

            filled_log: Dict[str, str] = {}
            unfilled_list: List[str] = []
            resume_attached = False

            # 3. Fill text/email/tel inputs
            for field in report.inputs:
                field_key = field_mapper.identify_field_type(field)
                if field_key:
                    cand_value = field_mapper.get_candidate_value(field_key, profile)
                    if cand_value:
                        try:
                            # Use locator based on semantic selector
                            locator = page.locator(field.selector).first
                            await locator.fill(cand_value)
                            filled_log[field_key] = cand_value
                            logger.info(f"Filled input '{field_key}' with '{cand_value}'")
                        except Exception as e:
                            logger.warning(f"Could not fill input '{field.selector}': {e}")
                            unfilled_list.append(field.name or field.selector)
                    else:
                        unfilled_list.append(field_key)
                else:
                    unfilled_list.append(field.name or field.selector)

            # 4. Handle file inputs (Resume upload)
            if report.file_inputs:
                file_field = report.file_inputs[0]
                upload_path = self._resolve_resume_path(resume_file_path)
                if upload_path and upload_path.exists():
                    try:
                        file_locator = page.locator(file_field.selector).first
                        await file_locator.set_input_files(str(upload_path))
                        # Verify attachment in DOM
                        attached_count = await page.evaluate(f"""() => {{
                            const input = document.querySelector('{file_field.selector}');
                            return input && input.files ? input.files.length : 0;
                        }}""")
                        if attached_count > 0:
                            resume_attached = True
                            filled_log["resume_file"] = upload_path.name
                            logger.info(f"Attached resume file: {upload_path.name}")
                        else:
                            unfilled_list.append("resume_attachment_failed")
                    except Exception as e:
                        logger.warning(f"File upload error: {e}")
                        unfilled_list.append("resume_upload_error")
                else:
                    unfilled_list.append("resume_file_missing_on_disk")

            # 5. Handle selects and dropdowns
            for select_field in report.selects:
                option, is_ambiguous = field_mapper.resolve_select_option(select_field, profile)
                if option and not is_ambiguous:
                    try:
                        select_locator = page.locator(select_field.selector).first
                        await select_locator.select_option(label=option)
                        filled_log[select_field.name or "select"] = option
                    except Exception as e:
                        logger.warning(f"Failed to select option '{option}': {e}")
                        unfilled_list.append(select_field.name or "select")
                else:
                    # Flag ambiguous choice for human review
                    unfilled_list.append(f"select_ambiguous:{select_field.name or select_field.id}")

            # 6. Handle textareas (open-ended questions - left for Part H AI reasoning or human review)
            for textarea in report.textareas:
                unfilled_list.append(f"textarea_question:{textarea.name or textarea.id}")

            # 7. STOP BEFORE SUBMISSION (Phase 31 requirement)
            logger.info("Application form draft prepared. STOPPED before submission.")

            return ApplicationDraftResult(
                job_id=job.id,
                status="READY",
                application_url=job.url,
                source=job.source,
                filled_fields=filled_log,
                unfilled_fields=unfilled_list,
                resume_attached=resume_attached,
                stopped_before_submission=True,
                notes=f"Successfully filled {len(filled_log)} fields; {len(unfilled_list)} fields require review."
            )
        finally:
            if own_context:
                await page.close()
                await context.close()

    def _resolve_resume_path(self, custom_path: Optional[str]) -> Optional[Path]:
        """Resolve valid resume file on disk."""
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)

        # Check default uploads directory or fallback test resume
        default_dir = Path("uploads")
        if default_dir.exists():
            for f in default_dir.iterdir():
                if f.suffix.lower() in {".pdf", ".docx"}:
                    return f

        return None


application_agent = ApplicationAgent()
