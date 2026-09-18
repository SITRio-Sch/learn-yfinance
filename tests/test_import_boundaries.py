"""AST and textual boundary tests enforcing architectural import and API constraints."""

from __future__ import annotations

import ast
from pathlib import Path


def _get_project_py_files() -> list[Path]:
    root = Path(__file__).parent.parent
    src_files = list((root / "src").rglob("*.py"))
    root_files = [root / "app.py", root / "launcher.py"]
    return [f for f in src_files + root_files if f.exists()]


def test_only_yfinance_provider_imports_yfinance():
    """Verify that ONLY yfinance_provider.py imports the yfinance library."""
    allowed_file = Path("src/yf_learner/providers/yfinance_provider.py")

    for file_path in _get_project_py_files():
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        imports_yfinance = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "yfinance" or alias.name.startswith("yfinance."):
                        imports_yfinance = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "yfinance" or (node.module and node.module.startswith("yfinance.")):
                    imports_yfinance = True

        if imports_yfinance:
            assert file_path.name == "yfinance_provider.py", (
                f"Prohibited import of yfinance found in {file_path}. "
                f"Only {allowed_file} is permitted to import yfinance."
            )


def test_no_prohibited_apis_and_direct_http():
    """Verify absence of prohibited APIs like yf.download, options, screeners, direct Yahoo HTTP."""
    prohibited_terms = [
        "yf.download",
        ".download(",
        "urllib.request",
        "requests.get",
        "requests.post",
        "http.client",
        "query1.finance.yahoo.com",
        "query2.finance.yahoo.com",
        ".options",
        "ticker.options",
        ".option_chain",
        "option_chain(",
        ".screeners",
        "screeners(",
    ]

    for file_path in _get_project_py_files():
        # Allow yfinance_provider to be the sole boundary
        if file_path.name == "yfinance_provider.py":
            continue

        content = file_path.read_text(encoding="utf-8")
        for term in prohibited_terms:
            assert term not in content, (
                f"Prohibited pattern '{term}' found in {file_path}."
            )
