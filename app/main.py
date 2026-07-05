"""VCA-Studio desktop entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import webview

import config
from api.bridge import build_api

DEV_URL = "http://localhost:5173?desktop=1"


def _url(dev: bool) -> str:
    if dev:
        return DEV_URL
    index = Path(config.DIST_INDEX)
    if not index.exists():
        raise FileNotFoundError(f"Frontend build not found: {index}")
    return index.as_uri()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Load Vite dev server")
    args = parser.parse_args()

    api = build_api()
    window = webview.create_window(
        config.APP_TITLE,
        _url(args.dev),
        js_api=api,
        width=1200,
        height=780,
        min_size=(960, 640),
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
