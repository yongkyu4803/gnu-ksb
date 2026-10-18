"""Opt-in live smoke check. Start uvicorn first; requires internet to UniProt."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def run():
    with sync_playwright() as p:
        options = {"headless": True}
        if os.environ.get("BROWSER_CHANNEL"):
            options["channel"] = os.environ["BROWSER_CHANNEL"]
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(os.environ.get("APP_URL", "http://127.0.0.1:8000"))
        page.locator("#target").fill("P04637 2\nP04637 1")
        page.locator("#candidates").fill("P04637\nP04637-2\nQ00987\nBAD")
        with page.expect_response("**/api/v1/jobs/preview", timeout=120000) as pending:
            page.locator("#generate").click()
        response = pending.value
        assert response.ok, response.text()
        expected = response.json()
        page.locator("#download").wait_for(state="visible")
        assert page.locator("#download").is_enabled()
        assert "최종 4개" in page.locator("#plans-table").inner_text()
        assert expected["summary"] == {"total": 4, "included": 3, "excluded": 1}
        with page.expect_download() as pending_download:
            page.locator("#download").click()
        download = pending_download.value
        assert json.loads(Path(download.path()).read_text()) == expected["jobs"]
        page.locator("#plans-table button").first.click()
        assert page.locator("#sequence-text").inner_text() == expected["plans"][0]["candidate"]["sequence"]
        output = Path("test-results")
        output.mkdir(exist_ok=True)
        page.screenshot(path=str(output / "desktop.png"), full_page=True)
        page.locator("#label").fill("changed")
        assert page.locator("#download").is_disabled()
        assert page.locator("#jobs-results").is_hidden()
        page.locator("#tab-lookup").click()
        page.locator("#lookup-ids").fill("P04637 P04637-2 BAD")
        with page.expect_response("**/api/v1/proteins/lookup", timeout=120000):
            page.locator("#lookup-submit").click()
        page.locator("#lookup-table tbody tr").first.wait_for()
        assert page.locator("#lookup-table tbody tr").count() == 3
        assert "P04637-2" in page.locator("#lookup-table").inner_text()
        # A late response must not revive the old preview after input changes.
        page.locator("#tab-jobs").click()
        page.route("**/api/v1/jobs/preview", lambda route: route.fulfill(json=expected))
        page.evaluate("""() => {
            document.getElementById('jobs-form').requestSubmit();
            const input = document.getElementById('label');
            input.value = 'edited during request';
            input.dispatchEvent(new Event('input', {bubbles:true}));
        }""")
        page.wait_for_function("!document.getElementById('generate').disabled")
        assert page.locator("#download").is_disabled()
        assert page.locator("#jobs-results").is_hidden()
        page.unroute("**/api/v1/jobs/preview")
        page.locator("#target").fill("BAD")
        page.locator("#generate").click()
        page.wait_for_function("document.getElementById('jobs-status').classList.contains('error')")
        assert "타겟 조회" in page.locator("#jobs-status").inner_text()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(output / "mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
        print("PASS: live lookup, isoform, self copies, partial failure, download equality, input/late response invalidation, target error, mobile layout")


if __name__ == "__main__":
    run()
