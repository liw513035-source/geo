"""Start the API and the web app together."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def main() -> int:
    api = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT / "apps" / "api",
    )
    web = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"],
        cwd=ROOT / "apps" / "web",
    )
    try:
        while True:
            if api.poll() is not None:
                return api.returncode or 0
            if web.poll() is not None:
                return web.returncode or 0
            try:
                api.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        return 0
    finally:
        for process in (api, web):
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
