"""Parse Grafana/Loki exports of nginx-ingress access logs into a canonical
DataFrame.

Canonical schema (one row per request):

    timestamp              (datetime64[ns, UTC])
    ip                     (str)
    method                 (str)
    path                   (str)         e.g. "/products/foo"
    query                  (str)         raw query string after "?", or ""
    full_url               (str)         path + ("?" + query) if query
    status                 (int)
    bytes                  (int)
    latency_ms             (float)       NaN if not present in log format
    user_agent             (str)
    claimed_bot            (str)         e.g. "Googlebot", "bingbot", or ""
    has_params             (bool)

The Streamlit upload widget hands us bytes; we accept either a path or a
str/bytes blob. Three input shapes are supported:

* Loki JSON (Grafana Explore "Inspector -> Data" download, or the Loki HTTP API
  response). Multiple sub-shapes auto-detected.
* CSV (Grafana Explore "Download CSV"). Looks for a `Line`/`line` column.
* Plain text: one nginx access-log line per row.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd

# --------------------------------------------------------------------------- #
# nginx access-log line parser
# --------------------------------------------------------------------------- #

# Combined log format with optional ingress-extra tail fields.
# We capture only what we need; the tail is matched non-greedily.
_NGINX_RE = re.compile(
    r"^(?P<ip>\S+)\s+"
    r"\S+\s+\S+\s+"  # ident, user
    r"\[(?P<time_local>[^\]]+)\]\s+"
    r'"(?P<method>[A-Z]+)\s+(?P<request_uri>[^"]*?)\s+(?P<protocol>HTTP/[\d.]+)"\s+'
    r"(?P<status>\d{3})\s+"
    r"(?P<bytes>\d+|-)\s+"
    r'"(?P<referer>[^"]*)"\s+'
    r'"(?P<user_agent>[^"]*)"'
    r"(?:\s+(?P<request_length>\d+|-)\s+(?P<request_time>[\d.]+|-))?"
)

_TIME_LOCAL_FMT = "%d/%b/%Y:%H:%M:%S %z"

_BOT_PATTERNS = [
    ("Googlebot-Image", re.compile(r"Googlebot-Image", re.I)),
    ("Googlebot-Video", re.compile(r"Googlebot-Video", re.I)),
    ("Googlebot-News", re.compile(r"Googlebot-News", re.I)),
    ("AdsBot-Google", re.compile(r"AdsBot-Google", re.I)),
    ("Mediapartners-Google", re.compile(r"Mediapartners-Google", re.I)),
    ("Googlebot", re.compile(r"Googlebot", re.I)),
    ("bingbot", re.compile(r"bingbot", re.I)),
    ("YandexBot", re.compile(r"YandexBot", re.I)),
    ("DuckDuckBot", re.compile(r"DuckDuckBot", re.I)),
    ("Baiduspider", re.compile(r"Baiduspider", re.I)),
]


@dataclass
class _Parsed:
    timestamp: datetime | None
    ip: str
    method: str
    path: str
    query: str
    status: int
    bytes_: int
    latency_ms: float
    user_agent: str
    referer: str


def _classify_claimed_bot(user_agent: str) -> str:
    for name, pattern in _BOT_PATTERNS:
        if pattern.search(user_agent):
            return name
    return ""


def parse_nginx_line(line: str) -> _Parsed | None:
    """Parse a single nginx access-log line. Returns None if it doesn't match."""
    m = _NGINX_RE.match(line.strip())
    if not m:
        return None
    g = m.groupdict()
    try:
        ts = datetime.strptime(g["time_local"], _TIME_LOCAL_FMT).astimezone(timezone.utc)
    except ValueError:
        ts = None

    request_uri = g["request_uri"] or "/"
    if "?" in request_uri:
        path, query = request_uri.split("?", 1)
    else:
        path, query = request_uri, ""

    bytes_ = int(g["bytes"]) if g["bytes"] and g["bytes"] != "-" else 0
    rt = g.get("request_time")
    latency_ms = float(rt) * 1000.0 if rt and rt != "-" else float("nan")
    referer = g.get("referer") or ""
    if referer == "-":
        referer = ""

    return _Parsed(
        timestamp=ts,
        ip=g["ip"],
        method=g["method"],
        path=path,
        query=query,
        status=int(g["status"]),
        bytes_=bytes_,
        latency_ms=latency_ms,
        user_agent=g["user_agent"],
        referer=referer,
    )


# --------------------------------------------------------------------------- #
# Loki JSON envelope handlers
# --------------------------------------------------------------------------- #


def _iter_loki_json_lines(payload: Any) -> Iterable[tuple[str | None, str]]:
    """Yield (timestamp_str_or_none, raw_line) from any of the common Loki/
    Grafana JSON shapes.

    Shapes supported:

    * ``{"streams": [{"stream": {...}, "values": [[ts_ns, line], ...]}]}``
      (Loki HTTP API "query_range" / "tail" format).
    * ``{"data": {"result": [{"stream": {...}, "values": [[ts_ns, line], ...]}],
                  "resultType": "streams"}}``
      (Loki API result wrapped, or older Grafana export).
    * ``{"results": {"A": {"frames": [{"schema": ..., "data": {"values": [...]}}]}}}``
      (Grafana DataFrame format from newer Explore exports).
    * ``[{"ts": ..., "line": ...}, ...]`` or NDJSON of the same.
    """
    # Grafana DataFrame format
    if isinstance(payload, dict) and "results" in payload:
        for _qid, qres in payload["results"].items():
            for frame in qres.get("frames", []) or []:
                yield from _iter_grafana_frame(frame)
        return

    # Loki API streams format (top-level "streams" or "data.result")
    streams = None
    if isinstance(payload, dict):
        if "streams" in payload:
            streams = payload["streams"]
        elif "data" in payload and isinstance(payload["data"], dict):
            streams = payload["data"].get("result")
    if streams is not None:
        for s in streams:
            for entry in s.get("values", []) or []:
                if len(entry) >= 2:
                    yield entry[0], entry[1]
        return

    # Flat list of objects
    if isinstance(payload, list):
        for obj in payload:
            if not isinstance(obj, dict):
                continue
            line = obj.get("line") or obj.get("Line") or obj.get("log")
            ts = obj.get("ts") or obj.get("Time") or obj.get("timestamp")
            if line:
                yield ts, line
        return


def _iter_grafana_frame(frame: dict[str, Any]) -> Iterable[tuple[str | None, str]]:
    """Yield (ts, line) tuples from a single Grafana DataFrame frame."""
    schema = frame.get("schema", {}) or {}
    fields = schema.get("fields", []) or []
    data = frame.get("data", {}) or {}
    columns = data.get("values", []) or []
    if not fields or not columns:
        return

    name_to_idx = {f.get("name", "").lower(): i for i, f in enumerate(fields)}
    line_idx = name_to_idx.get("line") or name_to_idx.get("body")
    if line_idx is None:
        # Some frames use "Line" / "Body" -- try original casing
        for i, f in enumerate(fields):
            if f.get("name", "").lower() in ("line", "body"):
                line_idx = i
                break
    time_idx = name_to_idx.get("time") or name_to_idx.get("timestamp") or name_to_idx.get("tsns")

    if line_idx is None or line_idx >= len(columns):
        return
    lines = columns[line_idx]
    times = columns[time_idx] if time_idx is not None and time_idx < len(columns) else [None] * len(lines)
    for ts, line in zip(times, lines):
        if line:
            yield (str(ts) if ts is not None else None), line


def _normalise_ts(ts: str | int | float | None, fallback: datetime | None) -> datetime | None:
    """Normalise a Loki timestamp (ns string, ms int, ISO string) to UTC datetime."""
    if ts is None or ts == "":
        return fallback
    if isinstance(ts, (int, float)):
        # Heuristic: ns vs ms vs s
        v = float(ts)
        if v > 1e17:
            return datetime.fromtimestamp(v / 1e9, tz=timezone.utc)
        if v > 1e14:
            return datetime.fromtimestamp(v / 1e6, tz=timezone.utc)
        if v > 1e11:
            return datetime.fromtimestamp(v / 1e3, tz=timezone.utc)
        return datetime.fromtimestamp(v, tz=timezone.utc)
    s = str(ts)
    if s.isdigit():
        return _normalise_ts(int(s), fallback)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return fallback


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #


def _row_from_line(line: str, envelope_ts: datetime | None) -> dict[str, Any] | None:
    parsed = parse_nginx_line(line)
    if parsed is None:
        return None
    ts = parsed.timestamp or envelope_ts
    full_url = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return {
        "timestamp": ts,
        "ip": parsed.ip,
        "method": parsed.method,
        "path": parsed.path,
        "query": parsed.query,
        "full_url": full_url,
        "status": parsed.status,
        "bytes": parsed.bytes_,
        "latency_ms": parsed.latency_ms,
        "user_agent": parsed.user_agent,
        "referer": parsed.referer,
        "claimed_bot": _classify_claimed_bot(parsed.user_agent),
        "has_params": bool(parsed.query),
    }


def parse_loki_json(text: str) -> pd.DataFrame:
    payload = json.loads(text)
    rows: list[dict[str, Any]] = []
    for ts_str, line in _iter_loki_json_lines(payload):
        env_ts = _normalise_ts(ts_str, None)
        row = _row_from_line(line, env_ts)
        if row is not None:
            rows.append(row)
    return _to_dataframe(rows)


def parse_ndjson(text: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: maybe this line is already a raw nginx access-log line
            # (e.g. someone concatenated logs without JSON-encoding them).
            row = _row_from_line(raw, None)
            if row is not None:
                rows.append(row)
            continue

        # Three valid shapes per line:
        #   1. JSON-encoded string  ->  the unescaped nginx line itself
        #      (this is what Grafana's "Download as JSONL" produces for raw logs)
        #   2. dict with a "line"/"log"/"message" field containing the nginx line
        #   3. dict where the nginx fields are already broken out
        if isinstance(obj, str):
            row = _row_from_line(obj, None)
            if row is not None:
                rows.append(row)
            continue

        if not isinstance(obj, dict):
            continue

        line = obj.get("line") or obj.get("Line") or obj.get("log") or obj.get("message")
        ts = obj.get("ts") or obj.get("Time") or obj.get("timestamp") or obj.get("time")
        env_ts = _normalise_ts(ts, None)
        if line:
            row = _row_from_line(line, env_ts)
            if row is not None:
                rows.append(row)
    return _to_dataframe(rows)


def parse_csv(text: str) -> pd.DataFrame:
    """Grafana Explore CSV download: usually has Time + Line + extracted labels."""
    df_raw = pd.read_csv(io.StringIO(text))
    # Find the line column
    line_col = next((c for c in df_raw.columns if c.lower() in ("line", "body", "log", "message")), None)
    if line_col is None:
        # Last resort: use the longest-mean-length column
        line_col = max(df_raw.columns, key=lambda c: df_raw[c].astype(str).str.len().mean())
    time_col = next((c for c in df_raw.columns if c.lower() in ("time", "timestamp", "ts")), None)

    rows: list[dict[str, Any]] = []
    for _, r in df_raw.iterrows():
        line = str(r[line_col])
        env_ts = _normalise_ts(r[time_col] if time_col else None, None)
        row = _row_from_line(line, env_ts)
        if row is not None:
            rows.append(row)
    return _to_dataframe(rows)


def parse_text(text: str) -> pd.DataFrame:
    """Plain text: one nginx access-log line per row."""
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        row = _row_from_line(raw, None)
        if row is not None:
            rows.append(row)
    return _to_dataframe(rows)


def parse_log_file(name: str, content: bytes | str) -> pd.DataFrame:
    """Top-level dispatcher. Picks a parser based on filename extension and
    falls back through the others if it returns nothing.
    """
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""

    order: list[str]
    if suffix == "json":
        order = ["json", "ndjson", "csv", "txt"]
    elif suffix == "csv":
        order = ["csv", "json", "ndjson", "txt"]
    elif suffix in ("ndjson", "jsonl"):
        order = ["ndjson", "json", "csv", "txt"]
    else:
        order = ["txt", "json", "ndjson", "csv"]

    for kind in order:
        try:
            df = _PARSERS[kind](text)
        except Exception:
            df = pd.DataFrame()
        if not df.empty:
            return df
    return _to_dataframe([])


_PARSERS = {
    "json": parse_loki_json,
    "ndjson": parse_ndjson,
    "csv": parse_csv,
    "txt": parse_text,
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_SCHEMA: dict[str, str] = {
    "timestamp": "datetime64[ns, UTC]",
    "ip": "string",
    "method": "string",
    "path": "string",
    "query": "string",
    "full_url": "string",
    "status": "Int64",
    "bytes": "Int64",
    "latency_ms": "float64",
    "user_agent": "string",
    "referer": "string",
    "claimed_bot": "string",
    "has_params": "boolean",
}


def _to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        df = pd.DataFrame({c: pd.Series(dtype=t) for c, t in _SCHEMA.items()})
        return df
    df = pd.DataFrame(rows)
    # Coerce types
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    for col, dtype in _SCHEMA.items():
        if col in df.columns and col not in ("timestamp",):
            try:
                df[col] = df[col].astype(dtype)
            except (TypeError, ValueError):
                pass
    # Sort by timestamp for downstream convenience
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return df
