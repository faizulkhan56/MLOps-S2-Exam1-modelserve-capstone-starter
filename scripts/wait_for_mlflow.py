"""
Block until the MLflow tracking server responds (HTTP 200 on /).
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000").rstrip("/")
TIMEOUT_SEC = float(os.environ.get("MLFLOW_WAIT_TIMEOUT_SEC", "120"))


def main() -> None:
    deadline = time.monotonic() + TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(URI + "/", timeout=3)
            print(f"MLflow is reachable at {URI}", file=sys.stderr)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(2.0)
    print(f"Timeout waiting for MLflow at {URI}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
