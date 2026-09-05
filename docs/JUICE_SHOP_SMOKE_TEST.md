# OWASP Juice Shop benchmark smoke test

Date: 2026-08-31

Decision: **PASS — suitable as the proposed repro v1 benchmark target.**

This was a suitability test, not a benchmark result. It validates one ordinary
shopping flow and one synthetic bug mechanism before the project is built.

## Environment

- URL: http://127.0.0.1:3000
- Container binding: loopback only
- Container image ID: sha256:73c53fbf442e8337b3ea3d98c7e8550308854701ebdfce4cc39768f36b75430e
- Image repository digest: bkimminich/juice-shop@sha256:73c53fbf442e8337b3ea3d98c7e8550308854701ebdfce4cc39768f36b75430e
- Architecture: arm64
- Playwright: 1.62.0
- Browser: Chromium
- Viewport: 1440 by 900
- Video decoder: FFmpeg and ffprobe

The image or a stable version tag must be pinned when the real corpus is
created. Do not silently move the benchmark to a new Juice Shop release.

## Flow tested

1. Open Juice Shop.
2. Dismiss the welcome and cookie overlays.
3. Open search.
4. Search for "Apple" and press Enter.
5. Resolve the exact "Apple Juice (1000ml)" product card.
6. Click its "Add to Basket" button.
7. Observe the basket count.
8. In fixed mode, open the basket page.

Fresh browser contexts were used so each run began with a basket count of zero.

## Repeatability result

| Mode | Runs | Basket transition | Final state | Result |
|---|---:|---|---|---|
| Fixed | 3 | 0 to 1 in all runs | Navigated to /#/basket | 3/3 passed |
| Buggy | 1 | 0 to 0 | Remained on search results | Passed |

The synthetic bug blocks only the Apple Juice add-to-basket click in the
capture phase. This simulates a broken or detached event handler. The fault is
installed by the benchmark harness and is not exposed to the repro pipeline.

An attempted network-failure fault was rejected because Juice Shop updates its
basket optimistically before the failed product request completes. That would
not produce the intended visible no-op bug.

## Accessibility and grounding suitability

After dismissing the two startup dialogs:

- ARIA snapshot: 180 lines.
- Referenced semantic nodes: 176.
- Nodes with bounding boxes: 178.
- Visible interactive candidates: 45.
- Raw buttons: 27.
- Search button with stable accessible name: exactly 1.
- Basket button with stable accessible name: exactly 1.
- "Add to Basket" buttons on the initial page: 16.

This is a useful grounding environment:

- Important global controls have meaningful accessible names.
- Product cards provide ancestor context.
- Many buttons intentionally share the same accessible name.
- Search for "Apple" returns Apple Juice, Apple Pomace, and Pineapple Juice.
- A naive substring locator for "Apple Juice" also matched "Pineapple Juice."

The Apple/Pineapple collision is a concrete example of why repro needs exact
lexical evidence, semantic evidence, ancestor context, and spatial information
instead of trusting a single string match.

Known accessibility weakness: the basket page did not expose the expected
main landmark during an exploratory read. Its controls and page snapshot were
still available, so this is not a blocker, but the final candidate extractor
must not assume every page contains a main element.

## Video suitability

The buggy flow produced a valid Playwright video:

- Codec: VP8.
- Resolution: 1440 by 900.
- Frame rate: 25 fps.
- Duration: 10.08 seconds.
- Size: 765,410 bytes.
- ffprobe decoded its metadata successfully.

A benchmark-only red cursor and click ripple are visible in the video. This
makes synthetic click timing observable. The assistance must be disclosed, and
human-recorded videos must be evaluated separately.

## Artifacts

- Machine-readable result: artifacts/smoke/smoke-results.json
- Accessibility summary: artifacts/smoke/accessibility-probe.json
- Initial ARIA snapshot: artifacts/smoke/initial-aria.txt
- Basket ARIA snapshot: artifacts/smoke/basket-aria.txt
- Before/after screenshots: artifacts/smoke/*.png
- Buggy-flow video: artifacts/smoke/video/*.webm
- Repeatable script: scripts/smoke_juice_shop.py

Run again while the target container is available:

~~~powershell
py scripts/smoke_juice_shop.py
~~~

The script deletes and recreates only artifacts/smoke, which contains generated
smoke-test output.

## Remaining caveats

- Only one flow was tested.
- Authentication, checkout, quantity changes, and application reset still need
  validation while building the corpus.
- The benchmark must keep fault definitions and generating locators separate
  from inputs visible to repro.
- Synthetic videos are easier than human recordings.
- Security-challenge functionality is out of scope and should not enter flows.
- The app's startup dialogs require deterministic dismissal.
- Exact image pinning may need a platform-specific policy if the benchmark is
  run on both arm64 and amd64 machines.

## Recommendation

Use OWASP Juice Shop for the v1 benchmark. Begin with two fully labeled flows
and expand only after the benchmark harness proves that fixed mode, buggy mode,
video, and ground truth remain aligned.
