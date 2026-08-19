"""Newline-delimited JSON sidecar process for the Tauri desktop shell."""

from __future__ import annotations

import json
import sys
from typing import TextIO

from rigmanifest.ipc import handle_request


def serve(input_stream: TextIO, output_stream: TextIO, *, once: bool = False) -> None:
    """Read one JSON object per line and emit exactly one response per request."""

    for raw_line in input_stream:
        if not raw_line.strip():
            continue
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            response = handle_request(request)
        except (json.JSONDecodeError, ValueError) as error:
            response = {
                "id": None,
                "error": {"code": "INVALID_JSON", "message": str(error)},
            }
        output_stream.write(json.dumps(response, separators=(",", ":")) + "\n")
        output_stream.flush()
        if once:
            break


def main() -> None:
    serve(sys.stdin, sys.stdout, once="--once" in sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
