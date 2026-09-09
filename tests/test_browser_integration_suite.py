import asyncio
import pytest
from backend.app.browser.browser import browser_service
from backend.app.browser.field_mapper import field_mapper
from backend.app.agents.application_agent import application_agent
from backend.app.models.job import Job
from backend.app.models.resume import CandidateProfile, CandidateDetails

COMPLEX_APPLICATION_FORM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Engineering Role Application</title>
  <style>
    .form-group { margin-bottom: 12px; }
    .error-text { color: red; font-size: 12px; display: none; }
  </style>
</head>
<body>
  <h1>Apply for Lead Infrastructure Engineer</h1>
  <form id="complex-job-form">
    <!-- Standard Fields -->
    <div class="form-group">
      <label for="c_first_name">Candidate First Name *</label>
      <input type="text" id="c_first_name" name="first_name" required aria-required="true" />
    </div>

    <div class="form-group">
      <label for="c_last_name">Candidate Family / Last Name *</label>
      <input type="text" id="c_last_name" name="last_name" required />
    </div>

    <div class="form-group">
      <label for="c_email">Work / Primary Email Address *</label>
      <input type="email" id="c_email" name="email" required />
    </div>

    <div class="form-group">
      <label for="c_phone">Contact Phone Number</label>
      <input type="tel" id="c_phone" name="phone" />
    </div>

    <div class="form-group">
      <label for="c_linkedin">LinkedIn Profile URL</label>
      <input type="url" id="c_linkedin" name="linkedin_profile" placeholder="https://linkedin.com/in/..." />
    </div>

    <!-- Select field with options -->
    <div class="form-group">
      <label for="c_work_auth">Are you authorized to work in this location? *</label>
      <select id="c_work_auth" name="work_authorization" required>
        <option value="">-- Please Select --</option>
        <option value="yes">Yes, authorized</option>
        <option value="no">No, need sponsorship</option>
      </select>
    </div>

    <!-- Textarea screening question -->
    <div class="form-group">
      <label for="c_motivation">Why do you want to work at our company?</label>
      <textarea id="c_motivation" name="why_company" rows="4"></textarea>
    </div>

    <!-- File upload -->
    <div class="form-group">
      <label for="c_resume_file">Attach Resume / CV *</label>
      <input type="file" id="c_resume_file" name="resume" accept=".pdf,.doc,.docx" />
    </div>

    <button type="submit" id="submit-application-btn">Submit Your Application</button>
  </form>
</body>
</html>
"""


def test_field_detection_on_complex_page():
    """
    Phase 45: Integration test verifying DOM tree inspection, field discovery,
    and semantic field type classification.
    """
    async def _test():
        data_url = f"data:text/html,{COMPLEX_APPLICATION_FORM_HTML}"
        page, context, nav_result, own_context = await browser_service.open_page(data_url)
        try:
            report = await browser_service.inspect_page_structure(page)
            assert report.total_fields >= 5
            assert len(report.inputs) >= 4

            # Test semantic field identification
            identified = {}
            for field in report.inputs:
                ftype = field_mapper.identify_field_type(field)
                if ftype:
                    identified[ftype] = field.name or field.id

            assert "first_name" in identified
            assert "last_name" in identified
            assert "email" in identified
            assert "phone" in identified

            # Test candidate value retrieval
            profile = CandidateProfile(
                candidate=CandidateDetails(
                    name="Jane Smith",
                    email="jane.smith@example.com",
                    phone="+1-555-0199",
                    linkedin="https://linkedin.com/in/janesmith"
                )
            )
            assert field_mapper.get_candidate_value("first_name", profile) == "Jane"
            assert field_mapper.get_candidate_value("last_name", profile) == "Smith"
            assert field_mapper.get_candidate_value("email", profile) == "jane.smith@example.com"
        finally:
            if own_context:
                await page.close()
                await context.close()

    asyncio.run(_test())


def test_autofill_and_safety_halt_before_submission():
    """
    Phase 45: Integration test verifying Playwright form autofill runs safely
    and stops unconditionally BEFORE clicking any submit button.
    """
    async def _test():
        data_url = f"data:text/html,{COMPLEX_APPLICATION_FORM_HTML}"
        job = Job(
            id=999,
            title="Lead Infrastructure Engineer",
            company="CloudScale Systems",
            location="Remote",
            remote=True,
            description="Kubernetes, Terraform, and Python infrastructure.",
            url=data_url,
            source="greenhouse"
        )
        profile = CandidateProfile(
            candidate=CandidateDetails(
                name="Alex Mercer",
                email="alex.mercer@example.com",
                phone="555-0123"
            )
        )

        draft = await application_agent.prepare_application_draft(job=job, profile=profile)
        assert draft.status == "READY"
        assert draft.stopped_before_submission is True
        assert draft.filled_fields.get("first_name") == "Alex"
        assert draft.filled_fields.get("email") == "alex.mercer@example.com"

    asyncio.run(_test())
