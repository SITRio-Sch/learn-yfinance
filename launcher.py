"""Launcher script to start the Streamlit application on 127.0.0.1:8501."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    app_path = (Path(__file__).parent / "app.py").resolve()
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
    ]
    # Pass along any extra arguments passed to launcher.py
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])

    try:
        proc = subprocess.run(cmd)
        return proc.returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
