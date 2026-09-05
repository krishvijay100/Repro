"""Repeatable suitability smoke test for the repro benchmark target.

This script is intentionally separate from the future repro implementation. It
checks whether OWASP Juice Shop is stable, accessible to Playwright, easy to
automate, and compatible with an isolated synthetic fault.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright


BASE_URL = "http://127.0.0.1:3000"
VIEWPORT = {"width": 1440, "height": 900}
OUTPUT_DIR = Path("artifacts/smoke")


CURSOR_OVERLAY_SCRIPT = r"""
(() => {
  const install = () => {
    if (!document.body || document.getElementById("repro-smoke-cursor")) return;
    const cursor = document.createElement("div");
    cursor.id = "repro-smoke-cursor";
    Object.assign(cursor.style, {
      position: "fixed",
      width: "16px",
      height: "16px",
      border: "3px solid #ff2d55",
      borderRadius: "50%",
      background: "rgba(255, 45, 85, 0.18)",
      pointerEvents: "none",
      zIndex: "2147483647",
      transform: "translate(-50%, -50%)",
      left: "0px",
      top: "0px",
    });
    document.body.appendChild(cursor);
    document.addEventListener("mousemove", event => {
      cursor.style.left = event.clientX + "px";
      cursor.style.top = event.clientY + "px";
    }, true);
    document.addEventListener("click", event => {
      const ripple = document.createElement("div");
      Object.assign(ripple.style, {
        position: "fixed",
        left: (event.clientX - 18) + "px",
        top: (event.clientY - 18) + "px",
        width: "36px",
        height: "36px",
        border: "3px solid #ff2d55",
        borderRadius: "50%",
        pointerEvents: "none",
        zIndex: "2147483646",
        opacity: "1",
        transition: "all 450ms ease-out",
      });
      document.body.appendChild(ripple);
      requestAnimationFrame(() => {
        ripple.style.transform = "scale(1.8)";
        ripple.style.opacity = "0";
      });
      setTimeout(() => ripple.remove(), 500);
    }, true);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
"""


@dataclass
class FlowResult:
    mode: str
    run: int
    passed: bool
    initial_add_buttons: int
    search_result_count: int
    target_article_count: int
    target_add_button_count: int
    cart_before: int
    cart_after: int
    final_url: str
    relevant_requests: list[dict[str, str]]
    error: str | None = None
    video_path: str | None = None


def basket_count(page: Page) -> int:
    text = page.get_by_role(
        "button", name="Show the shopping cart", exact=True
    ).inner_text()
    matches = re.findall(r"\d+", text)
    if not matches:
        raise AssertionError(f"No basket count found in {text!r}")
    return int(matches[-1])


def dismiss_startup_overlays(page: Page) -> None:
    page.get_by_role(
        "button", name="Close Welcome Banner", exact=True
    ).click()
    page.get_by_role(
        "button", name="dismiss cookie message", exact=True
    ).click()


def collect_accessibility_probe(
    page: Page, dialogs_before_dismissal: int
) -> dict[str, Any]:
    snapshot = page.aria_snapshot(mode="ai", boxes=True)
    (OUTPUT_DIR / "initial-aria.txt").write_text(snapshot, encoding="utf-8")
    page.screenshot(path=OUTPUT_DIR / "initial-page.png", full_page=True)

    interactive = page.locator(
        "button, a[href], input, textarea, select, "
        "[role=button], [role=link], [role=textbox], [contenteditable=true]"
    )
    visible_interactive = sum(
        1 for index in range(interactive.count()) if interactive.nth(index).is_visible()
    )

    return {
        "title": page.title(),
        "url": page.url,
        "snapshot_lines": len(snapshot.splitlines()),
        "snapshot_refs": len(re.findall(r"\[ref=e\d+\]", snapshot)),
        "snapshot_boxes": len(re.findall(r"\[box=", snapshot)),
        "raw_buttons": page.locator("button").count(),
        "raw_links": page.locator("a").count(),
        "raw_inputs": page.locator("input").count(),
        "visible_interactive_candidates": visible_interactive,
        "dialogs_before_dismissal": dialogs_before_dismissal,
        "dialogs_after_dismissal": page.get_by_role("dialog").count(),
        "named_open_search_buttons": page.get_by_role(
            "button", name="Open search", exact=True
        ).count(),
        "named_cart_buttons": page.get_by_role(
            "button", name="Show the shopping cart", exact=True
        ).count(),
    }


def install_bug(page: Page) -> None:
    page.evaluate(
        r"""
        () => {
          document.addEventListener("click", event => {
            const button = event.target.closest(
              'button[aria-label="Add to Basket"]'
            );
            const article = button && button.closest("mat-card");
            if (
              article &&
              article.innerText.trim().startsWith("Apple Juice (1000ml)")
            ) {
              event.preventDefault();
              event.stopImmediatePropagation();
            }
          }, true);
        }
        """
    )


def run_flow(
    browser: Browser,
    mode: str,
    run_number: int,
    *,
    record_video: bool = False,
) -> FlowResult:
    video_dir = OUTPUT_DIR / "video"
    context_options: dict[str, Any] = {"viewport": VIEWPORT}
    if record_video:
        video_dir.mkdir(parents=True, exist_ok=True)
        context_options.update(
            record_video_dir=str(video_dir),
            record_video_size=VIEWPORT,
        )

    context = browser.new_context(**context_options)
    context.add_init_script(CURSOR_OVERLAY_SCRIPT)
    page = context.new_page()
    page.set_default_timeout(8_000)

    relevant_requests: list[dict[str, str]] = []
    page.on(
        "request",
        lambda request: relevant_requests.append(
            {
                "method": request.method,
                "resource_type": request.resource_type,
                "url": request.url,
            }
        )
        if "/api/Products/" in request.url
        else None,
    )

    result = FlowResult(
        mode=mode,
        run=run_number,
        passed=False,
        initial_add_buttons=0,
        search_result_count=0,
        target_article_count=0,
        target_add_button_count=0,
        cart_before=-1,
        cart_after=-1,
        final_url="",
        relevant_requests=relevant_requests,
    )

    video = page.video if record_video else None

    try:
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(1_200)

        dialogs_before_dismissal = page.get_by_role("dialog").count()
        dismiss_startup_overlays(page)
        page.wait_for_timeout(300 if not record_video else 900)

        if run_number == 1 and mode == "fixed":
            probe = collect_accessibility_probe(
                page, dialogs_before_dismissal
            )
            (OUTPUT_DIR / "accessibility-probe.json").write_text(
                json.dumps(probe, indent=2), encoding="utf-8"
            )

        result.initial_add_buttons = page.get_by_role(
            "button", name="Add to Basket", exact=True
        ).count()

        page.get_by_role("button", name="Open search", exact=True).click()
        search = page.get_by_role("textbox")
        if search.count() != 1:
            raise AssertionError(f"Expected one search textbox, got {search.count()}")

        search.fill("Apple")
        search.press("Enter")
        page.wait_for_timeout(900 if not record_video else 1_500)

        articles = page.get_by_role("article")
        result.search_result_count = articles.count()
        target = articles.filter(
            has_text=re.compile(r"^Apple Juice \(1000ml\)")
        )
        result.target_article_count = target.count()
        add_button = target.get_by_role(
            "button", name="Add to Basket", exact=True
        )
        result.target_add_button_count = add_button.count()
        result.cart_before = basket_count(page)

        if mode == "buggy":
            install_bug(page)

        page.screenshot(
            path=OUTPUT_DIR / f"{mode}-run-{run_number}-before-add.png",
            full_page=True,
        )
        page.wait_for_timeout(300 if not record_video else 1_000)
        add_button.click()
        page.wait_for_timeout(1_000 if not record_video else 2_000)
        result.cart_after = basket_count(page)
        page.screenshot(
            path=OUTPUT_DIR / f"{mode}-run-{run_number}-after-add.png",
            full_page=True,
        )

        expected_count = 1 if mode == "fixed" else 0
        if result.cart_before != 0:
            raise AssertionError(
                f"Expected a fresh basket count of 0, got {result.cart_before}"
            )
        if result.cart_after != expected_count:
            raise AssertionError(
                f"Expected {mode} basket count {expected_count}, "
                f"got {result.cart_after}"
            )

        if mode == "fixed":
            page.get_by_role(
                "button", name="Show the shopping cart", exact=True
            ).click()
            page.wait_for_timeout(600)
            if not page.url.endswith("/#/basket"):
                raise AssertionError(f"Unexpected basket URL: {page.url}")
            basket_snapshot = page.aria_snapshot(mode="ai", boxes=True)
            (OUTPUT_DIR / "basket-aria.txt").write_text(
                basket_snapshot, encoding="utf-8"
            )
            page.screenshot(
                path=OUTPUT_DIR / "basket-page.png", full_page=True
            )

        result.final_url = page.url
        result.passed = True
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        result.final_url = page.url
        page.screenshot(
            path=OUTPUT_DIR / f"{mode}-run-{run_number}-error.png",
            full_page=True,
        )
    finally:
        context.close()
        if video is not None:
            try:
                result.video_path = str(video.path())
            except Exception as exc:
                result.error = (
                    (result.error + "; ") if result.error else ""
                ) + f"VideoError: {exc}"
                result.passed = False

    return result


def probe_video(video_path: str) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=codec_name,width,height,avg_frame_rate",
        "-of",
        "json",
        video_path,
    ]
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def main() -> int:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: list[FlowResult] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for run_number in range(1, 4):
            results.append(run_flow(browser, "fixed", run_number))
        results.append(
            run_flow(browser, "buggy", 1, record_video=True)
        )
        browser.close()

    video_result = next(
        result for result in results if result.mode == "buggy"
    )
    video_probe = (
        probe_video(video_result.video_path)
        if video_result.video_path
        else None
    )

    report = {
        "target": {
            "base_url": BASE_URL,
            "viewport": VIEWPORT,
            "fault": (
                "Block the Apple Juice Add to Basket click in the capture phase"
            ),
        },
        "results": [asdict(result) for result in results],
        "video_probe": video_probe,
        "all_passed": all(result.passed for result in results),
    }
    report_path = OUTPUT_DIR / "smoke-results.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nReport: {report_path.resolve()}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
