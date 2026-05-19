"""Command-line entry point.

Resolves the bundled Streamlit app and pages/ directory inside the installed
package and hands control to Streamlit's own CLI. Any extra arguments after
``seo-log-auditor`` are forwarded to ``streamlit run``.

Examples
--------
    seo-log-auditor                                   # default port 8501, 500 MB upload cap
    seo-log-auditor --server.port 9000                # forward Streamlit flags
    SEO_LOG_AUDITOR_MAX_UPLOAD_MB=1024 seo-log-auditor  # 1 GB upload cap
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_MAX_UPLOAD_MB = "500"


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

    extra_args = list(sys.argv[1:])

    # The .streamlit/config.toml at the repo root never makes it into the
    # wheel, so we can't rely on it for end users. Inject a generous default
    # upload cap here. Users override either with the explicit Streamlit flag
    # or with the SEO_LOG_AUDITOR_MAX_UPLOAD_MB env var.
    if not any(a.startswith("--server.maxUploadSize") for a in extra_args):
        max_mb = os.environ.get("SEO_LOG_AUDITOR_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)
        extra_args = ["--server.maxUploadSize", max_mb, *extra_args]

    sys.argv = ["streamlit", "run", str(app_path), *extra_args]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
