"""
Every call to Yahoo Finance lives here, wrapped in Streamlit's cache.

Caching matters more than it looks: Yahoo throttles aggressively, and a
Streamlit script re-runs top to bottom on every widget interaction. Without
these caches, changing the chart period would re-download eleven years of
prices.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

PRICE_TTL = 60 * 30       # 30 minutes
FUNDAMENTAL_TTL = 60 * 60 * 12  # 12 hours


def _strip_timezone(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None:
        frame = frame.copy()
        frame.index = frame.index.tz_localize(None)
    return frame


@st.cache_data(ttl=PRICE_TTL, show_spinner=False)
def get_price_history(ticker: str, period: str = "max") -> pd.DataFrame:
    """Daily OHLCV, adjusted for splits and dividends, tz-naive index."""
    try:
        frame = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception:
        return pd.DataFrame()
    if frame is None or frame.empty:
        return pd.DataFrame()
    return _strip_timezone(frame)


@st.cache_data(ttl=FUNDAMENTAL_TTL, show_spinner=False)
def get_info(ticker: str) -> dict:
    """
    Yahoo's summary payload. Patchy for Indian listings, so every consumer
    must treat missing keys as normal rather than exceptional.
    """
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    return dict(info)


@st.cache_data(ttl=FUNDAMENTAL_TTL, show_spinner=False)
def get_statements(ticker: str) -> dict[str, pd.DataFrame]:
    """Annual income statement, balance sheet and cash flow."""
    empty = pd.DataFrame()
    try:
        handle = yf.Ticker(ticker)
        return {
            "income": handle.income_stmt if handle.income_stmt is not None else empty,
            "balance": handle.balance_sheet if handle.balance_sheet is not None else empty,
            "cashflow": handle.cashflow if handle.cashflow is not None else empty,
        }
    except Exception:
        return {"income": empty, "balance": empty, "cashflow": empty}


@st.cache_data(ttl=FUNDAMENTAL_TTL, show_spinner=False)
def get_market_cap(ticker: str) -> float | None:
    """
    Cheap market-cap lookup used to rank potential peers. fast_info is a much
    lighter request than the full info payload.
    """
    try:
        fast = yf.Ticker(ticker).fast_info
        cap = fast.get("market_cap") if hasattr(fast, "get") else None
        if cap:
            return float(cap)
    except Exception:
        pass
    try:
        cap = get_info(ticker).get("marketCap")
        return float(cap) if cap else None
    except Exception:
        return None
