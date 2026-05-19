# seo-log-auditor

Streamlit dashboard that ingests a 30-day Grafana/Loki export of nginx-ingress
Googlebot logs and runs seven SEO crawl-audit techniques on it:

1. **Crawl budget distribution** – how hits are spread across page types vs
   how URLs are spread across page types.
2. **Orphan pages** – URLs Googlebot is hitting that are not in your sitemap.
3. **Status-code waste** – non-200 ratio per page type, redirect chains.
4. **Stale high-value pages** – sitemap URLs not crawled in the last N days.
5. **Performance** – page-size vs latency vs hit frequency.
6. **Bot verification** – verified Googlebot vs spoofed User-Agents.
7. **Parameter traps** – paths with an explosive number of query-string variants.

## Quick start

Zero-install via [uv](https://docs.astral.sh/uv/):

```bash
uvx seo-log-auditor
```

Or install into the current environment:

```bash
pip install seo-log-auditor
seo-log-auditor
```

Either command launches the dashboard at <http://localhost:8501>. To pass
flags through to Streamlit:

```bash
seo-log-auditor --server.port 9000 --server.headless true
```

Then in the sidebar:

1. Upload your Grafana/Loki export (`.json`, `.csv`, or `.txt`).
2. Paste your sitemap URL (a sitemap index works too).
3. Optionally upload a `page_patterns.yaml` (see
   `src/seo_log_auditor/config/page_patterns.example.yaml`).

## Exporting logs from Grafana

Use this LogQL query in Grafana Explore against your Loki datasource:

```
{app="ingress-nginx"} |= "Googlebot"
```

Set the time range to **last 30 days** and download as **JSON** (best fidelity)
or CSV. Plain `.txt` (one log line per row) also works.

## Page-pattern config

`src/seo_log_auditor/config/page_patterns.example.yaml` is the starting point.
First match wins. Edit it for your URL structure and re-upload via the
sidebar. Tagging traps like `paginated` and `faceted` as their own page types
makes leakage immediately visible on the Crawl Budget page.

## Development

```bash
git clone https://github.com/hitensangani/seo-log-auditor.git
cd seo-log-auditor
uv sync --extra dev
uv run streamlit run src/seo_log_auditor/app.py
```

### Project layout

```
src/seo_log_auditor/
  app.py                        # Streamlit entry, sidebar uploads, KPI overview
  cli.py                        # `seo-log-auditor` console script
  pages/                        # Multipage app, one file per technique
  config/                       # Example page-pattern rules
  parsers.py                    # Loki JSON / CSV / nginx-text -> DataFrame
  classify.py                   # Regex-based URL -> page_type
  sitemap.py                    # Fetch + parse sitemap.xml (incl. index)
  verify_bot.py                 # Google IP ranges + cached reverse DNS
  analysis/                     # One module per technique
tests/                          # pytest fixtures + unit tests
```

### Running tests

```bash
uv run pytest
```

## Roadmap

- Internal-link-depth correlation (technique 4 deeper layer) once you have a
  Screaming Frog / Sitebulb export.
- Direct Loki API streaming so you don't need to download files.
- SQLite cache for week-over-week comparisons.

## License

MIT — see [LICENSE](LICENSE).
