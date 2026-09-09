import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.async_api import Page, BrowserContext

from backend.app.browser.browser import browser_service
from backend.app.browser.field_mapper import field_mapper
from backend.app.models.application import Application, SubmissionResult
from backend.app.models.job import Job
from backend.app.models.resume import CandidateProfile

logger = logging.getLogger("ai_job_agent.submission_agent")


class SubmissionAgent:
    """
    Phase 38: Controlled Application Submission Agent.
    Phase 39: Failure Recovery & Loop Prevention.

    Strict Human-in-the-Loop Gate:
    ONLY applications in APPROVED status can be submitted.
    Halts immediately upon validation errors or CAPTCHAs without retrying.
    """

    SUBMIT_BUTTON_SELECTORS = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Submit Application")',
        'button:has-text("Submit")',
        'button:has-text("Apply Now")',
        'button:has-text("Apply")',
        'button:has-text("Send Application")'
    ]

    ERROR_SELECTORS = [
        '.error',
        '.field-error',
        '.invalid-feedback',
        '.alert-danger',
        '[aria-invalid="true"]',
        '.error-message'
    ]

    CAPTCHA_SELECTORS = [
        'iframe[src*="recaptcha"]',
        'iframe[src*="turnstile"]',
        'iframe[src*="hcaptcha"]',
        '.g-recaptcha',
        '.cf-turnstile',
        '#recaptcha'
    ]

    CONFIRMATION_PATTERNS = [
        "thank you",
        "application submitted",
        "application received",
        "we have received your application",
        "successfully submitted",
        "thanks for applying",
        "application complete"
    ]

    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    async def submit_application(
        self,
        application: Application,
        job: Job,
        profile: CandidateProfile,
        resume_file_path: Optional[str] = None
    ) -> SubmissionResult:
        """
        Execute controlled final submission for an APPROVED application.
        Strictly enforces the approval gate and terminates safely on any error.
        """
        # Phase 38 Strict Check: Approval required
        if application.status != "APPROVED":
            raise ValueError(
                f"Application #{application.id} cannot be submitted: current status is '{application.status}'. "
                f"Application must be explicitly APPROVED by the user before submission."
            )

        logger.info(f"Initiating controlled submission for approved application #{application.id} ({job.title} at {job.company})...")

        page, context, nav_result, own_context = await browser_service.open_page(job.url)
        timestamp = int(time.time())

        try:
            # 1. Fill standard approved fields
            filled_fields = dict(application.filled_fields or {})
            for field_key, value in filled_fields.items():
                if not value or field_key in ["resume_file"]:
                    continue
                try:
                    # Look for element by name, id, or placeholder
                    selector = f'input[name="{field_key}"], #{field_key}, input[placeholder*="{field_key}"]'
                    locator = page.locator(selector).first
                    if await locator.count() > 0:
                        await locator.fill(str(value))
                        logger.debug(f"Submission: filled field '{field_key}'")
                except Exception as e:
                    logger.debug(f"Submission: soft ignore filling field '{field_key}': {e}")

            # 2. Fill answers to screening questions
            answers = dict(application.answers or {})
            for q_id, ans_data in answers.items():
                ans_text = ans_data.get("answer") if isinstance(ans_data, dict) else str(ans_data)
                if ans_text:
                    try:
                        q_locator = page.locator(f'[name="{q_id}"], #{q_id}').first
                        if await q_locator.count() > 0:
                            tag_name = await q_locator.evaluate("el => el.tagName.toLowerCase()")
                            if tag_name == "select":
                                await q_locator.select_option(label=ans_text)
                            else:
                                await q_locator.fill(ans_text)
                    except Exception as e:
                        logger.debug(f"Submission: could not set answer for '{q_id}': {e}")

            # 3. Fill cover letter if present
            if application.cover_letter:
                try:
                    cl_locator = page.locator('textarea[name*="cover"], textarea[id*="cover"], #cover_letter').first
                    if await cl_locator.count() > 0:
                        await cl_locator.fill(application.cover_letter)
                except Exception as e:
                    logger.debug(f"Submission: cover letter field not filled: {e}")

            # 4. Attach resume if file input present
            try:
                file_input = page.locator('input[type="file"]').first
                if await file_input.count() > 0:
                    resume_path = self._resolve_resume_path(resume_file_path)
                    if resume_path and resume_path.exists():
                        await file_input.set_input_files(str(resume_path))
                        logger.info(f"Submission: attached resume {resume_path.name}")
            except Exception as e:
                logger.debug(f"Submission: resume input attach exception: {e}")

            # 5. Check for existing CAPTCHA challenge before submission
            for c_sel in self.CAPTCHA_SELECTORS:
                if await page.locator(c_sel).count() > 0:
                    screenshot_path = self.sessions_dir / f"submission_captcha_{application.id}_{timestamp}.png"
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.warning(f"Submission #{application.id} detected CAPTCHA challenge before submit. Halting safely.")
                    return SubmissionResult(
                        application_id=application.id,
                        success=False,
                        status="FAILED",
                        failure_reason="CAPTCHA challenge detected on application form. Halting safely without retrying.",
                        screenshot_path=str(screenshot_path)
                    )

            # 6. Locate Submit Button
            submit_btn = None
            for sel in self.SUBMIT_BUTTON_SELECTORS:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    submit_btn = btn
                    break

            if not submit_btn:
                screenshot_path = self.sessions_dir / f"submission_failed_nobtn_{application.id}_{timestamp}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                return SubmissionResult(
                    application_id=application.id,
                    success=False,
                    status="FAILED",
                    failure_reason="No visible submit button found on target application page.",
                    screenshot_path=str(screenshot_path)
                )

            # 7. CLICK SUBMIT (Single controlled click, no loops)
            logger.info(f"Submission: clicking submit button for application #{application.id}...")
            await submit_btn.click(timeout=5000, no_wait_after=True)

            # Wait briefly for page reaction / validation
            await page.wait_for_timeout(2000)

            # 7. Phase 39: Validation Error & CAPTCHA Detection (Failure Recovery)
            # Check for CAPTCHA
            for c_sel in self.CAPTCHA_SELECTORS:
                if await page.locator(c_sel).count() > 0:
                    screenshot_path = self.sessions_dir / f"submission_captcha_{application.id}_{timestamp}.png"
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.warning(f"Submission #{application.id} encountered CAPTCHA challenge. Halting safely.")
                    return SubmissionResult(
                        application_id=application.id,
                        success=False,
                        status="FAILED",
                        failure_reason="CAPTCHA challenge detected on submission. Halting safely without retrying.",
                        screenshot_path=str(screenshot_path)
                    )

            # Check for visible validation errors
            for err_sel in self.ERROR_SELECTORS:
                err_loc = page.locator(err_sel).first
                if await err_loc.count() > 0 and await err_loc.is_visible():
                    err_text = await err_loc.inner_text()
                    screenshot_path = self.sessions_dir / f"submission_validation_error_{application.id}_{timestamp}.png"
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.warning(f"Submission #{application.id} failed validation: {err_text}. Halting safely.")
                    return SubmissionResult(
                        application_id=application.id,
                        success=False,
                        status="FAILED",
                        failure_reason=f"Form validation error: {err_text.strip() or 'Field requirement not met'}",
                        screenshot_path=str(screenshot_path)
                    )

            # 8. Check for Confirmation / Success Outcome
            page_text = (await page.inner_text("body")).lower()
            current_url = page.url.lower()

            is_confirmed = False
            confirmation_msg = "Application submitted successfully."

            for pat in self.CONFIRMATION_PATTERNS:
                if pat in page_text or pat in current_url:
                    is_confirmed = True
                    confirmation_msg = f"Confirmed: '{pat}' detected on landing page."
                    break

            # If redirected to a thank you URL or confirmation
            if any(term in current_url for term in ["thank", "confirm", "success", "applied", "status"]):
                is_confirmed = True
                confirmation_msg = f"Redirected to confirmation page: {page.url}"

            # Take submission confirmation screenshot
            screenshot_path = self.sessions_dir / f"submission_confirmed_{application.id}_{timestamp}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            applied_time = datetime.now(timezone.utc)

            if is_confirmed:
                logger.info(f"Submission #{application.id} SUCCESS: {confirmation_msg}")
                return SubmissionResult(
                    application_id=application.id,
                    success=True,
                    status="SUBMITTED",
                    confirmation_message=confirmation_msg,
                    confirmation_url=page.url,
                    screenshot_path=str(screenshot_path),
                    applied_at=applied_time
                )
            else:
                # Page changed/submitted without explicit error or confirmation keyword
                logger.info(f"Submission #{application.id} finished with status SUBMITTED at {page.url}")
                return SubmissionResult(
                    application_id=application.id,
                    success=True,
                    status="SUBMITTED",
                    confirmation_message="Form submitted successfully (final landing URL recorded).",
                    confirmation_url=page.url,
                    screenshot_path=str(screenshot_path),
                    applied_at=applied_time
                )

        except Exception as e:
            logger.error(f"Submission #{application.id} encountered unexpected error: {e}")
            screenshot_path = self.sessions_dir / f"submission_exception_{application.id}_{timestamp}.png"
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                screenshot_path = None

            return SubmissionResult(
                application_id=application.id,
                success=False,
                status="FAILED",
                failure_reason=f"Browser automation error: {str(e)}",
                screenshot_path=str(screenshot_path) if screenshot_path else None
            )
        finally:
            if own_context:
                await page.close()
                await context.close()

    def _resolve_resume_path(self, custom_path: Optional[str]) -> Optional[Path]:
        """Find candidate resume file."""
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)

        uploads_dir = Path("uploads")
        if uploads_dir.exists():
            for f in uploads_dir.iterdir():
                if f.suffix.lower() in {".pdf", ".docx"}:
                    return f
        return None


submission_agent = SubmissionAgent()
