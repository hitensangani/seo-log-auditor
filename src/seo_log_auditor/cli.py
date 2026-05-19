"""Command-line entry point.

Resolves the bundled Streamlit app and pages/ directory inside the installed
package and hands control to Streamlit's own CLI. Any extra arguments after
``seo-log-auditor`` are forwarded to ``streamlit run``.

Examples
--------
    seo-log-auditor                        # default port 8501
    seo-log-auditor --server.port 9000     # forward Streamlit flags
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bundled_app_path() -> Path:
    return Path(__file__).resolve().parent / "app.py"


def main() -> None:
    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:  # pragma: no cover - install-time check
        sys.stderr.write(
            "Streamlit is not installed in this environment. Reinstall the "
            "package with `pip install seo-log-auditor` or run via "
            "`uvx seo-log-auditor`.\n"
        )
        raise SystemExit(1) from exc

    app_path = _bundled_app_path()
    if not app_path.is_file():
        sys.stderr.write(
            f"Could not locate bundled Streamlit app at {app_path}. "
            "This usually means the package is broken or partially installed.\n"
        )
        raise SystemExit(1)

    sys.argv = ["streamlit", "run", str(app_path), *sys.argv[1:]]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
