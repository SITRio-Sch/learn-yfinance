"""Root application entry point for Streamlit."""

from pathlib import Path
import sys

_SRC_DIR = Path(__file__).resolve().parent / "src"
_src_path = str(_SRC_DIR)
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from yf_learner.ui.app import render_app

if __name__ == "__main__":
    render_app()
