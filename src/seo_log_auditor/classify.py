"""Regex-based URL -> page_type classifier.

Loads a list of named patterns from a YAML config (the example one ships at
``config/page_patterns.example.yaml``). Patterns are evaluated in order and
the first matching pattern wins. Anything that matches no pattern is tagged
with the ``default`` value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import yaml


@dataclass(frozen=True)
class Pattern:
    name: str
    regex: re.Pattern[str]


@dataclass
class Classifier:
    patterns: list[Pattern]
    default: str = "other"

    def classify(self, url: str) -> str:
        for p in self.patterns:
            if p.regex.search(url):
                return p.name
        return self.default

    def classify_series(self, urls: Iterable[str]) -> pd.Series:
        return pd.Series([self.classify(u) for u in urls], dtype="string")


def load_classifier(yaml_text: str | bytes) -> Classifier:
    if isinstance(yaml_text, bytes):
        yaml_text = yaml_text.decode("utf-8")
    cfg = yaml.safe_load(yaml_text) or {}
    raw_patterns = cfg.get("patterns", []) or []
    patterns: list[Pattern] = []
    for entry in raw_patterns:
        name = entry.get("name")
        match = entry.get("match")
        if not name or not match:
            continue
        try:
            patterns.append(Pattern(name=name, regex=re.compile(match)))
        except re.error as exc:
            raise ValueError(f"Invalid regex for pattern '{name}': {match}") from exc
    default = cfg.get("default", "other")
    return Classifier(patterns=patterns, default=default)


def default_classifier() -> Classifier:
    """A reasonable starter classifier when the user hasn't supplied a yaml."""
    return Classifier(
        patterns=[
            Pattern("home", re.compile(r"^/?$")),
            Pattern("paginated", re.compile(r"[?&]page=")),
            Pattern("faceted", re.compile(r"[?&](sort|color|size|filter|price|brand)=")),
            Pattern("session_param", re.compile(r"[?&](sessionid|sid|phpsessid|utm_)")),
            Pattern("api", re.compile(r"^/api/")),
            Pattern("static_asset", re.compile(r"\.(?:js|css|png|jpe?g|gif|svg|webp|woff2?|ico)(?:$|\?)", re.IGNORECASE)),
        ],
        default="other",
    )


def add_page_type(df: pd.DataFrame, classifier: Classifier, column: str = "full_url") -> pd.DataFrame:
    """Return a new DataFrame with a ``page_type`` column appended."""
    df = df.copy()
    df["page_type"] = classifier.classify_series(df[column].fillna(""))
    return df
