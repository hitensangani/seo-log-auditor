# Security Policy

## Supported versions

`seo-log-auditor` is in active development pre-1.0. Only the latest released
version on PyPI receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security problems.**

If you've found a security issue — for example, a way the parser could be
tricked into executing code, a path-traversal in the launcher, or a way the
sitemap fetcher could be abused for SSRF — please report it privately:

1. Use [GitHub's private vulnerability reporting](https://github.com/hitensangani/seo-log-auditor/security/advisories/new) (preferred), or
2. Email me via the contact form at [hiten.eu](https://hiten.eu).

I aim to acknowledge reports within 72 hours and ship a fix within 14 days
for confirmed issues. Critical issues (RCE, data exfiltration) will be
prioritised.

## What's in scope

- The CLI (`seo-log-auditor`) and any subcommands.
- The Streamlit app (`src/seo_log_auditor/app.py` and `src/seo_log_auditor/pages/`).
- The log parsers (`src/seo_log_auditor/parsers.py`).
- The sitemap fetcher (`src/seo_log_auditor/sitemap.py`).
- Dependencies pinned in `pyproject.toml`.

## What's out of scope

- Issues that require physical access to the user's machine.
- Vulnerabilities in upstream dependencies that are already publicly
  disclosed (please report those upstream).
- Issues only reproducible with deliberately malformed log files where the
  user *intended* to crash the parser. Crashing on bad input is a robustness
  bug, not a security bug — please open a normal issue.
- Browser-cache or session-state issues that don't involve code execution
  or data exfiltration. The app is local-only and all data is per-session.

## Privacy guarantees

`seo-log-auditor` is designed to keep your log data local. The app makes no
network calls except:

- Fetching the sitemap URL you provide.
- Fetching Google's published [crawler IP ranges](https://developers.google.com/search/apis/ipranges/googlebot.json).
- Optional reverse-DNS lookups to verify Googlebot IPs.

If you discover the app making any other outbound connection, that's a
security bug — please report it.

## Disclosure policy

Once a fix is shipped, a [security advisory](https://github.com/hitensangani/seo-log-auditor/security/advisories) will be
published crediting the reporter (unless they prefer to stay anonymous).

— Hiten Sangani · [hiten.eu](https://hiten.eu)
