import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from backend.app.browser.models import (
    FormDiagnosticReport,
    FormFieldDiagnostic,
    PageNavigationResult,
)

logger = logging.getLogger("ai_job_agent.browser")

TuplePageNavigation = Tuple[Page, BrowserContext, PageNavigationResult, bool]


class BrowserService:
    """
    Centralized Playwright browser automation service managing lifecycle,
    isolated session contexts, page inspection, and safe authentication.
    """

    def __init__(self, sessions_dir: str = "sessions"):
        self._sessions_dir = Path(sessions_dir)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self.default_timeout_ms = 20000

    async def initialize(self, headless: bool = True):
        """Launch and centralize browser instance."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        if not self._browser or not self._browser.is_connected():
            logger.info(f"Launching Playwright Chromium (headless={headless})...")
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )

    async def close(self):
        """Cleanly shutdown browser and Playwright driver."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser service closed.")

    async def create_isolated_context(
        self,
        session_name: Optional[str] = None
    ) -> BrowserContext:
        """
        Create an isolated browser context.
        If a session_name is provided and exists, loads persisted storage state.
        """
        if not self._browser:
            await self.initialize(headless=True)

        storage_state_path = None
        if session_name:
            session_file = self._sessions_dir / f"{session_name}.json"
            if session_file.exists():
                storage_state_path = str(session_file)
                logger.info(f"Loading session storage state from {storage_state_path}")

        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            storage_state=storage_state_path
        )
        context.set_default_timeout(self.default_timeout_ms)
        return context

    async def save_session(self, context: BrowserContext, session_name: str) -> Path:
        """Persist session cookies and localStorage safely without storing plain credentials."""
        target = self._sessions_dir / f"{session_name}.json"
        await context.storage_state(path=str(target))
        logger.info(f"Saved session state to {target}")
        return target

    async def open_page(
        self,
        url: str,
        context: Optional[BrowserContext] = None
    ) -> TuplePageNavigation:
        """
        Open target application URL, wait for DOM content, and capture page title & final URL.
        """
        own_context = False
        if context is None:
            context = await self.create_isolated_context()
            own_context = True

        page = await context.new_page()
        start_time = time.time()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.default_timeout_ms)
            load_time = round((time.time() - start_time) * 1000, 2)
            title = await page.title()
            final_url = page.url
            status_code = response.status if response else 200

            nav_result = PageNavigationResult(
                url=url,
                final_url=final_url,
                title=title or "Untitled",
                status_code=status_code,
                load_time_ms=load_time
            )
            return page, context, nav_result, own_context
        except Exception as e:
            if own_context:
                await context.close()
            raise e

    async def inspect_page_structure(self, page: Page) -> FormDiagnosticReport:
        """
        Deep semantic inspection of visible text and form controls:
        inputs, selects, textareas, file inputs, and action buttons.
        """
        title = await page.title()
        url = page.url

        # JavaScript evaluation to inspect elements directly in DOM
        form_data = await page.evaluate("""() => {
            const getLabel = (el) => {
                // 1. Direct label element via for/id
                if (el.id) {
                    const label = document.querySelector(`label[for="${el.id}"]`);
                    if (label) return label.innerText.trim();
                }
                // 2. Parent label
                const parentLabel = el.closest('label');
                if (parentLabel) return parentLabel.innerText.trim();
                // 3. aria-label or placeholder
                return el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
            };

            const inputs = Array.from(document.querySelectorAll('input')).map(el => ({
                tag: 'input',
                field_type: el.type || 'text',
                name: el.name || null,
                id: el.id || null,
                placeholder: el.placeholder || null,
                label: getLabel(el),
                aria_label: el.getAttribute('aria-label') || null,
                required: el.required || el.getAttribute('aria-required') === 'true',
                options: [],
                selector: el.id ? `#${el.id}` : (el.name ? `input[name="${el.name}"]` : 'input')
            }));

            const selects = Array.from(document.querySelectorAll('select')).map(el => ({
                tag: 'select',
                field_type: 'select',
                name: el.name || null,
                id: el.id || null,
                placeholder: null,
                label: getLabel(el),
                aria_label: el.getAttribute('aria-label') || null,
                required: el.required || false,
                options: Array.from(el.options).map(o => o.text.trim()),
                selector: el.id ? `#${el.id}` : (el.name ? `select[name="${el.name}"]` : 'select')
            }));

            const textareas = Array.from(document.querySelectorAll('textarea')).map(el => ({
                tag: 'textarea',
                field_type: 'textarea',
                name: el.name || null,
                id: el.id || null,
                placeholder: el.placeholder || null,
                label: getLabel(el),
                aria_label: el.getAttribute('aria-label') || null,
                required: el.required || false,
                options: [],
                selector: el.id ? `#${el.id}` : (el.name ? `textarea[name="${el.name}"]` : 'textarea')
            }));

            const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]'))
                .map(b => b.innerText?.trim() || b.value?.trim() || 'Submit')
                .filter(Boolean);

            return { inputs, selects, textareas, buttons };
        }""")

        raw_inputs = form_data.get("inputs", [])
        raw_selects = form_data.get("selects", [])
        raw_textareas = form_data.get("textareas", [])
        raw_buttons = form_data.get("buttons", [])

        # Separate file inputs
        file_inputs = [FormFieldDiagnostic(**i) for i in raw_inputs if i["field_type"] == "file"]
        standard_inputs = [FormFieldDiagnostic(**i) for i in raw_inputs if i["field_type"] != "file"]
        select_fields = [FormFieldDiagnostic(**s) for s in raw_selects]
        textarea_fields = [FormFieldDiagnostic(**t) for t in raw_textareas]

        report = FormDiagnosticReport(
            url=url,
            page_title=title or "Page",
            total_fields=len(raw_inputs) + len(raw_selects) + len(raw_textareas),
            inputs=standard_inputs,
            selects=select_fields,
            textareas=textarea_fields,
            file_inputs=file_inputs,
            buttons=raw_buttons
        )

        return report

    def save_diagnostic_report(self, report: FormDiagnosticReport, out_path: Optional[str] = None) -> Path:
        """Save form diagnostics to JSON representation for debugging."""
        if not out_path:
            out_path = self._sessions_dir / "latest_form_diagnostic.json"
        else:
            out_path = Path(out_path)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)
        logger.info(f"Diagnostic report saved to {out_path}")
        return out_path

browser_service = BrowserService()

