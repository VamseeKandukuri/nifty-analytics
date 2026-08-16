"""
Loads the Nifty 50 / 100 / 200 / 500 constituent lists.

Primary source: the official constituent CSVs published by NSE Indices.
Those files already carry the company name, the NSE symbol and NSE's own
macro-economic industry classification, so the whole universe (including the
industry a stock belongs to) is derived rather than hand-maintained.

If NSE is unreachable (rate limiting, no outbound network, etc.) the app falls
back to the snapshot bundled in data/nifty_universe_fallback.csv so the site
still renders.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

NSE_BASE = "https://nsearchives.nseindia.com/content/indices/"

INDEX_FILES = {
    "NIFTY 50": "ind_nifty50list.csv",
    "NIFTY 100": "ind_nifty100list.csv",
    "NIFTY 200": "ind_nifty200list.csv",
    "NIFTY 500": "ind_nifty500list.csv",
}

# Narrowest to widest. A stock's "tier" is the narrowest index it belongs to.
TIER_ORDER = ["NIFTY 50", "NIFTY 100", "NIFTY 200", "NIFTY 500"]

FALLBACK_CSV = Path(__file__).resolve().parent.parent / "data" / "nifty_universe_fallback.csv"

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# A handful of NSE symbols do not map cleanly to a Yahoo Finance ticker.
SYMBOL_OVERRIDES: dict[str, str] = {
    "M&M": "M&M.NS",
    "M&MFIN": "M&MFIN.NS",
    "J&KBANK": "J&KBANK.NS",
    "ARE&M": "ARE&M.NS",
    "L&TFH": "LTF.NS",
}


def to_yahoo_ticker(nse_symbol: str) -> str:
    """Convert an NSE symbol (e.g. RELIANCE) to a Yahoo ticker (RELIANCE.NS)."""
    symbol = str(nse_symbol).strip().upper()
    if symbol in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[symbol]
    return f"{symbol}.NS"


def _download_index(filename: str, timeout: int = 12) -> pd.DataFrame:
    response = requests.get(NSE_BASE + filename, headers=_REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    frame.columns = [c.strip() for c in frame.columns]
    return frame


def _from_nse() -> pd.DataFrame:
    """Build the universe from the four live NSE constituent files."""
    collected: dict[str, dict] = {}

    # Walk widest -> narrowest so the narrowest membership wins the tier label.
    for tier in reversed(TIER_ORDER):
        frame = _download_index(INDEX_FILES[tier])
        for _, row in frame.iterrows():
            symbol = str(row["Symbol"]).strip().upper()
            collected[symbol] = {
                "symbol": symbol,
                "name": str(row["Company Name"]).strip(),
                "industry": str(row.get("Industry", "Unclassified")).strip() or "Unclassified",
                "tier": tier,
            }

    universe = pd.DataFrame(list(collected.values()))
    if universe.empty:
        raise ValueError("NSE returned an empty constituent list")
    return universe


def _from_fallback() -> pd.DataFrame:
    universe = pd.read_csv(FALLBACK_CSV)
    universe.columns = [c.strip().lower() for c in universe.columns]
    return universe


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_universe() -> tuple[pd.DataFrame, str]:
    """
    Return (universe_dataframe, source_label).

    Columns: symbol, name, industry, tier, ticker, label
    """
    try:
        universe = _from_nse()
        source = "NSE Indices (live)"
    except Exception:
        universe = _from_fallback()
        source = "bundled snapshot (NSE unreachable)"

    universe["industry"] = universe["industry"].fillna("Unclassified").replace("", "Unclassified")
    universe["ticker"] = universe["symbol"].map(to_yahoo_ticker)
    universe["label"] = universe["name"] + "  (" + universe["symbol"] + ")"
    universe["tier_rank"] = universe["tier"].map({t: i for i, t in enumerate(TIER_ORDER)})
    universe = universe.sort_values(["tier_rank", "name"]).reset_index(drop=True)
    return universe, source


def within_tier(universe: pd.DataFrame, tier: str) -> pd.DataFrame:
    """Nifty 200 includes everything in Nifty 50 and Nifty 100, and so on."""
    cutoff = TIER_ORDER.index(tier)
    return universe[universe["tier_rank"] <= cutoff].copy()


def industries_in(universe: pd.DataFrame) -> list[str]:
    return sorted(universe["industry"].dropna().unique().tolist())


def search(universe: pd.DataFrame, query: str) -> pd.DataFrame:
    """Case-insensitive match on company name or NSE symbol."""
    q = query.strip().lower()
    if not q:
        return universe.iloc[0:0]
    mask = universe["name"].str.lower().str.contains(q, regex=False) | universe[
        "symbol"
    ].str.lower().str.contains(q, regex=False)
    hits = universe[mask].copy()
    # Exact symbol match, then name-prefix match, float to the top.
    hits["rank"] = 2
    hits.loc[hits["name"].str.lower().str.startswith(q), "rank"] = 1
    hits.loc[hits["symbol"].str.lower() == q, "rank"] = 0
    return hits.sort_values(["rank", "name"]).drop(columns="rank")
