"""Technique 6: User-Agent masquerade.

Reads the ``is_verified_googlebot`` column added by ``verify_bot.add_verification``
and produces summary tables for the dashboard.
"""

from __future__ import annotations

import pandas as pd


def verification_summary(log_df: pd.DataFrame) -> dict[str, int | float]:
    if log_df.empty:
        return {"claimed": 0, "verified": 0, "spoofed": 0, "verified_share": 0.0}
    claimed_mask = log_df["claimed_bot"].fillna("").str.startswith(
        ("Googlebot", "AdsBot-Google", "Mediapartners-Google")
    )
    claimed = int(claimed_mask.sum())
    verified = int((claimed_mask & log_df["is_verified_googlebot"].fillna(False)).sum())
    spoofed = claimed - verified
    return {
        "claimed": claimed,
        "verified": verified,
        "spoofed": spoofed,
        "verified_share": verified / claimed if claimed else 0.0,
    }


def top_spoofers(log_df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["ip", "user_agent", "hits"])
    claimed_mask = log_df["claimed_bot"].fillna("").str.startswith(
        ("Googlebot", "AdsBot-Google", "Mediapartners-Google")
    )
    spoof = log_df[claimed_mask & ~log_df["is_verified_googlebot"].fillna(False)]
    if spoof.empty:
        return pd.DataFrame(columns=["ip", "user_agent", "hits"])
    grouped = (
        spoof.groupby(["ip", "user_agent"])
        .size()
        .rename("hits")
        .reset_index()
        .sort_values("hits", ascending=False)
        .head(top_n)
    )
    return grouped


def hits_by_verdict(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["verdict", "hits"])
    claimed_mask = log_df["claimed_bot"].fillna("").str.startswith(
        ("Googlebot", "AdsBot-Google", "Mediapartners-Google")
    )
    verified_col = log_df["is_verified_googlebot"].fillna(False)
    verdict = pd.Series("other", index=log_df.index, dtype="string")
    verdict.loc[claimed_mask & verified_col] = "verified Googlebot"
    verdict.loc[claimed_mask & ~verified_col] = "spoofed Googlebot"
    other_bot_mask = (~claimed_mask) & log_df["claimed_bot"].fillna("").ne("")
    verdict.loc[other_bot_mask] = "other declared bot"
    return (
        verdict.value_counts()
        .rename_axis("verdict")
        .rename("hits")
        .reset_index()
    )
