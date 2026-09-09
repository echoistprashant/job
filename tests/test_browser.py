import asyncio
import json
import pytest
from pathlib import Path
from backend.app.browser.browser import BrowserService
from backend.app.browser.models import FormDiagnosticReport


SAMPLE_APPLICATION_HTML = """
<!DOCTYPE html>
<html>
<head><title>Job Application - Senior AI Engineer</title></head>
<body>
  <h1>Apply for Senior AI Engineer</h1>
  <form id="app-form">
    <label for="fname">First Name:</label>
    <input type="text" id="fname" name="first_name" required placeholder="John" />

    <label for="lname">Last Name:</label>
    <input type="text" id="lname" name="last_name" required placeholder="Doe" />

    <label for="user-email">Email Address:</label>
    <input type="email" id="user-email" name="email" required placeholder="john@example.com" />

    <label for="phone">Phone Number:</label>
    <input type="tel" id="phone" name="phone" placeholder="+1-555-0199" />

    <label for="exp">Years of Experience:</label>
    <select id="exp" name="experience_years">
      <option value="0-1">0-1 years</option>
      <option value="2-4">2-4 years</option>
      <option value="5+">5+ years</option>
    </select>

    <label for="cover">Why are you interested in this role?</label>
    <textarea id="cover" name="cover_letter" placeholder="Tell us about yourself"></textarea>

    <label for="resume">Resume Attachment (PDF/DOCX):</label>
    <input type="file" id="resume" name="resume_file" accept=".pdf,.docx" required />

    <button type="submit">Submit Application</button>
  </form>
</body>
</html>
"""


def test_browser_lifecycle():
    """Phase 22 & 23: Test Playwright launch and centralized shutdown."""
    async def run():
        service = BrowserService(sessions_dir="test_sessions")
        await service.initialize(headless=True)
        assert service._browser is not None
        assert service._browser.is_connected()
        await service.close()
        assert service._browser is None

    asyncio.run(run())


def test_open_page_and_navigation():
    """Phase 24: Open application page and capture title, final URL, and timing."""
    async def run():
        service = BrowserService(sessions_dir="test_sessions")
        await service.initialize(headless=True)
        
        # Test navigation using data URL
        data_url = "data:text/html,<html><head><title>Test Job Portal</title></head><body><h1>Careers</h1></body></html>"
        page, context, nav_result, own_context = await service.open_page(data_url)

        try:
            assert nav_result.title == "Test Job Portal"
            assert "data:text/html" in nav_result.final_url
            assert nav_result.load_time_ms >= 0
        finally:
            await page.close()
            await context.close()
            await service.close()

    asyncio.run(run())


def test_inspect_page_structure():
    """Phase 25: Inspect form structure, detect inputs, selects, textareas, files, and save diagnostics."""
    async def run():
        service = BrowserService(sessions_dir="test_sessions")
        await service.initialize(headless=True)

        data_url = f"data:text/html,{SAMPLE_APPLICATION_HTML}"
        page, context, _, _ = await service.open_page(data_url)

        try:
            report: FormDiagnosticReport = await service.inspect_page_structure(page)
            assert report.page_title == "Job Application - Senior AI Engineer"
            assert report.total_fields >= 6

            # Check inputs
            input_names = [i.name for i in report.inputs]
            assert "first_name" in input_names
            assert "last_name" in input_names
            assert "email" in input_names
            assert "phone" in input_names

            # Check selects
            assert len(report.selects) == 1
            assert report.selects[0].name == "experience_years"
            assert "2-4 years" in report.selects[0].options

            # Check textarea
            assert len(report.textareas) == 1
            assert report.textareas[0].name == "cover_letter"

            # Check file upload input
            assert len(report.file_inputs) == 1
            assert report.file_inputs[0].name == "resume_file"
            assert report.file_inputs[0].field_type == "file"

            # Check buttons
            assert "Submit Application" in report.buttons

            # Save diagnostic file
            diag_file = service.save_diagnostic_report(report, out_path="test_sessions/diagnostic.json")
            assert Path(diag_file).exists()
            with open(diag_file, "r") as f:
                saved_json = json.load(f)
                assert saved_json["page_title"] == report.page_title

            # Clean test file
            Path(diag_file).unlink(missing_ok=True)
        finally:
            await page.close()
            await context.close()
            await service.close()

    asyncio.run(run())


def test_safe_session_isolation():
    """Phase 26: Verify isolated browser contexts and session state separation."""
    async def run():
        service = BrowserService(sessions_dir="test_sessions")
        await service.initialize(headless=True)

        # Context 1: Set a cookie
        ctx1 = await service.create_isolated_context()
        page1 = await ctx1.new_page()
        await page1.goto("data:text/html,<html><body><h1>Context 1</h1></body></html>")
        await ctx1.add_cookies([{
            "name": "auth_token",
            "value": "secret_session_token_123",
            "domain": "localhost",
            "path": "/"
        }])

        cookies1 = await ctx1.cookies()
        assert any(c["name"] == "auth_token" for c in cookies1)

        # Context 2: Should NOT have Context 1's cookies (isolated)
        ctx2 = await service.create_isolated_context()
        cookies2 = await ctx2.cookies()
        assert not any(c["name"] == "auth_token" for c in cookies2)

        await ctx1.close()
        await ctx2.close()
        await service.close()

        # Clean up test directory
        Path("test_sessions").rmdir() if Path("test_sessions").exists() and not list(Path("test_sessions").iterdir()) else None

    asyncio.run(run())
