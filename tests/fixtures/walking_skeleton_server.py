"""Local fixed/buggy page used only to verify the first vertical slice."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def page_html(mode: str) -> bytes:
    click_handler = (
        "document.querySelector('#basket-count').textContent = '1'"
        if mode == "fixed"
        else "void 0"
    )
    return f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>Repro fixture</title></head>
  <body>
    <article aria-label="Apple Juice product">
      <h2>Apple Juice</h2>
      <button onclick="{click_handler}">Add to Basket</button>
    </article>
    <article aria-label="Banana Juice product">
      <h2>Banana Juice</h2>
      <button>Add to Basket</button>
    </article>
    <button aria-label="Show the shopping cart">
      Basket: <span id="basket-count">0</span>
    </button>
  </body>
</html>""".encode()


class FixtureHandler(BaseHTTPRequestHandler):
    mode = "buggy"

    def do_GET(self) -> None:
        body = page_html(self.mode)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("buggy", "fixed"), required=True)
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    FixtureHandler.mode = arguments.mode
    ThreadingHTTPServer(("127.0.0.1", arguments.port), FixtureHandler).serve_forever()


if __name__ == "__main__":
    main()

