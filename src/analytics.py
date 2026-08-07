"""
All the number-crunching. Nothing here touches Streamlit widgets, so each
function can be tested on its own.

Two conventions used throughout:
  * Rupee amounts are converted to crore (1 crore = 10,000,000).
  * A value that cannot be computed comes back as NaN or None, never as 0.
    Zero is a real answer and must not stand in for "Yahoo didn't have it".
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import market_data

CRORE = 10_000_000

# ----------------------------------------------------------------------------
# Statement helpers
# ----------------------------------------------------------------------------

def _row(frame: pd.DataFrame, *candidates: str) -> pd.Series | None:
    """First matching line item from a yfinance statement, or None."""
    if frame is None or frame.empty:
        return None
    for name in candidates:
        if name in frame.index:
            series = pd.to_numeric(frame.loc[name], errors="coerce")
            if series.notna().any():
                return series
    return None


def _at(series: pd.Series | None, column) -> float:
    if series is None or column not in series.index:
        return np.nan
    value = series[column]
    return float(value) if pd.notna(value) else np.nan


def _safe_div(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


# ----------------------------------------------------------------------------
# 1. Snapshot cards
# ----------------------------------------------------------------------------

def snapshot(ticker: str, history: pd.DataFrame) -> dict:
    info = market_data.get_info(ticker)

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price and not history.empty:
        price = float(history["Close"].iloc[-1])

    previous = info.get("previousClose")
    if not previous and len(history) > 1:
        previous = float(history["Close"].iloc[-2])

    change_pct = np.nan
    if price and previous:
        change_pct = (price / previous - 1) * 100

    market_cap = info.get("marketCap")
    shares = info.get("sharesOutstanding")
    if not shares and market_cap and price:
        shares = market_cap / price

    return {
        "price": price,
        "change_pct": change_pct,
        "market_cap_cr": market_cap / CRORE if market_cap else np.nan,
        "shares_cr": shares / CRORE if shares else np.nan,
        "beta": info.get("beta"),
        "day_low": info.get("dayLow"),
        "day_high": info.get("dayHigh"),
        "week52_low": info.get("fiftyTwoWeekLow"),
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "sector": info.get("sector"),
        "long_name": info.get("longName"),
    }


# ----------------------------------------------------------------------------
# 2. Valuation multiples and peer comparison
# ----------------------------------------------------------------------------

def multiples(ticker: str) -> dict:
    """One row of the peer comparison table."""
    info = market_data.get_info(ticker)
    statements = market_data.get_statements(ticker)
    income = statements["income"]

    market_cap = info.get("marketCap")
    enterprise_value = info.get("enterpriseValue")

    # Yahoo publishes some of these directly; recompute the rest where possible.
    ev_ebitda = info.get("enterpriseToEbitda")
    ev_sales = info.get("enterpriseToRevenue")

    if (ev_ebitda is None or ev_sales is None) and enterprise_value and not income.empty:
        latest = income.columns[0]
        revenue = _at(_row(income, "Total Revenue", "Operating Revenue"), latest)
        ebitda = _at(_row(income, "EBITDA", "Normalized EBITDA"), latest)
        if ev_sales is None:
            ev_sales = _safe_div(enterprise_value, revenue)
        if ev_ebitda is None:
            ev_ebitda = _safe_div(enterprise_value, ebitda)

    return {
        "Price (Rs)": info.get("currentPrice") or info.get("regularMarketPrice"),
        "Mkt Cap (Rs Cr)": market_cap / CRORE if market_cap else np.nan,
        "EV (Rs Cr)": enterprise_value / CRORE if enterprise_value else np.nan,
        "P/E": info.get("trailingPE"),
        "Fwd P/E": info.get("forwardPE"),
        "P/B": info.get("priceToBook"),
        "EV/EBITDA": ev_ebitda,
        "EV/Sales": ev_sales,
        "ROE %": info.get("returnOnEquity") * 100 if info.get("returnOnEquity") else np.nan,
        "Div Yield %": info.get("dividendYield") if info.get("dividendYield") else np.nan,
    }


def pick_peers(universe: pd.DataFrame, row: pd.Series, count: int = 4,
               max_candidates: int = 12) -> list[str]:
    """
    Closest same-industry companies by market capitalisation.

    Size proximity beats alphabetical order here: comparing Reliance's EV/EBITDA
    against a small refiner's tells you less than comparing it against the other
    large integrated names.
    """
    candidates = universe[
        (universe["industry"] == row["industry"]) & (universe["symbol"] != row["symbol"])
    ]
    if candidates.empty:
        return []

    # Prefer peers of a similar index tier, then widen if that is too thin.
    same_tier = candidates[candidates["tier_rank"] <= row["tier_rank"]]
    if len(same_tier) >= count:
        candidates = same_tier

    candidates = candidates.head(max_candidates)

    self_cap = market_data.get_market_cap(row["ticker"])
    scored: list[tuple[float, str]] = []
    for _, candidate in candidates.iterrows():
        cap = market_data.get_market_cap(candidate["ticker"])
        if cap is None or cap <= 0:
            continue
        distance = abs(np.log(cap) - np.log(self_cap)) if self_cap else 0.0
        scored.append((distance, candidate["symbol"]))

    if not scored:
        return candidates["symbol"].head(count).tolist()

    scored.sort()
    return [symbol for _, symbol in scored[:count]]


def comparison_table(universe: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    rows = {}
    for symbol in symbols:
        match = universe[universe["symbol"] == symbol]
        if match.empty:
            continue
        entry = match.iloc[0]
        rows[f"{entry['symbol']}"] = multiples(entry["ticker"])
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).T


# ----------------------------------------------------------------------------
# 3. Five-year fundamentals
# ----------------------------------------------------------------------------

def fundamentals(ticker: str, years: int = 5) -> pd.DataFrame:
    statements = market_data.get_statements(ticker)
    income, balance, cashflow = statements["income"], statements["balance"], statements["cashflow"]

    if income is None or income.empty:
        return pd.DataFrame()

    revenue_row = _row(income, "Total Revenue", "Operating Revenue")
    gross_row = _row(income, "Gross Profit")
    cost_row = _row(income, "Cost Of Revenue", "Reconciled Cost Of Revenue")
    ebitda_row = _row(income, "EBITDA", "Normalized EBITDA")
    ebit_row = _row(income, "EBIT", "Operating Income")
    # `or` cannot be used to chain these: a pandas Series has no truth value.
    depreciation_row = _row(income, "Reconciled Depreciation")
    if depreciation_row is None:
        depreciation_row = _row(
            cashflow, "Depreciation And Amortization", "Depreciation Amortization Depletion"
        )
    net_row = _row(income, "Net Income", "Net Income Common Stockholders")
    eps_row = _row(income, "Diluted EPS", "Basic EPS")

    equity_row = _row(balance, "Stockholders Equity", "Total Equity Gross Minority Interest")
    assets_row = _row(balance, "Total Assets")
    curr_liab_row = _row(balance, "Current Liabilities", "Total Current Liabilities")

    periods = list(income.columns)[:years]
    records = []

    for index, period in enumerate(periods):
        revenue = _at(revenue_row, period)

        gross = _at(gross_row, period)
        if pd.isna(gross):
            cost = _at(cost_row, period)
            gross = revenue - cost if pd.notna(revenue) and pd.notna(cost) else np.nan

        ebitda = _at(ebitda_row, period)
        if pd.isna(ebitda):
            ebit = _at(ebit_row, period)
            depreciation = _at(depreciation_row, period)
            ebitda = ebit + depreciation if pd.notna(ebit) and pd.notna(depreciation) else np.nan

        net_income = _at(net_row, period)

        # Average balance-sheet denominators against the prior year where we
        # have one; a closing-balance ROE overstates a company that just raised
        # equity.
        prior = periods[index + 1] if index + 1 < len(periods) else None

        def averaged(series):
            current = _at(series, period)
            if prior is None:
                return current
            earlier = _at(series, prior)
            if pd.isna(earlier):
                return current
            return (current + earlier) / 2

        equity = averaged(equity_row)
        assets = averaged(assets_row)
        current_liabilities = averaged(curr_liab_row)
        capital_employed = (
            assets - current_liabilities
            if pd.notna(assets) and pd.notna(current_liabilities)
            else np.nan
        )

        ebit_value = _at(ebit_row, period)

        records.append({
            "Year": period.strftime("%b %Y") if hasattr(period, "strftime") else str(period),
            "Revenue (Rs Cr)": revenue / CRORE if pd.notna(revenue) else np.nan,
            "Revenue Growth %": np.nan,
            "Gross Margin %": _safe_div(gross, revenue) * 100,
            "EBITDA (Rs Cr)": ebitda / CRORE if pd.notna(ebitda) else np.nan,
            "EBITDA Margin %": _safe_div(ebitda, revenue) * 100,
            "Net Profit (Rs Cr)": net_income / CRORE if pd.notna(net_income) else np.nan,
            "PAT Margin %": _safe_div(net_income, revenue) * 100,
            "ROE %": _safe_div(net_income, equity) * 100,
            "ROCE %": _safe_div(ebit_value, capital_employed) * 100,
            "EPS (Rs)": _at(eps_row, period),
        })

    table = pd.DataFrame(records)
    if table.empty:
        return table

    # yfinance returns newest first; growth needs oldest first.
    table = table.iloc[::-1].reset_index(drop=True)
    table["Revenue Growth %"] = table["Revenue (Rs Cr)"].pct_change() * 100
    return table.set_index("Year")


# ----------------------------------------------------------------------------
# 4. Returns across horizons
# ----------------------------------------------------------------------------

HORIZONS = {
    "1M": 30, "6M": 182, "1Y": 365, "2Y": 730,
    "3Y": 1095, "5Y": 1826, "7Y": 2557, "10Y": 3653,
}


def returns_table(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()

    closes = history["Close"].dropna()
    if closes.empty:
        return pd.DataFrame()

    latest_price = float(closes.iloc[-1])
    latest_date = closes.index[-1]
    first_date = closes.index[0]

    records = []
    for label, days in HORIZONS.items():
        target = latest_date - dt.timedelta(days=days)

        # Refuse to quote a 10-year return for a company listed three years ago.
        if first_date > target + dt.timedelta(days=15):
            records.append({"Period": label, "Absolute %": np.nan, "Annualised (CAGR) %": np.nan})
            continue

        window = closes.loc[:target]
        if window.empty:
            records.append({"Period": label, "Absolute %": np.nan, "Annualised (CAGR) %": np.nan})
            continue

        past_price = float(window.iloc[-1])
        if past_price <= 0:
            records.append({"Period": label, "Absolute %": np.nan, "Annualised (CAGR) %": np.nan})
            continue

        absolute = (latest_price / past_price - 1) * 100
        years = days / 365.25
        annualised = ((latest_price / past_price) ** (1 / years) - 1) * 100

        records.append({
            "Period": label,
            "Absolute %": absolute,
            "Annualised (CAGR) %": annualised,
        })

    return pd.DataFrame(records).set_index("Period")


# ----------------------------------------------------------------------------
# 5. Distribution of periodic returns
# ----------------------------------------------------------------------------

BUCKET_EDGES = [-np.inf, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30, np.inf]
BUCKET_LABELS = [
    "< -30%", "-30 to -25%", "-25 to -20%", "-20 to -15%", "-15 to -10%",
    "-10 to -5%", "-5 to 0%", "0 to 5%", "5 to 10%", "10 to 15%",
    "15 to 20%", "20 to 25%", "25 to 30%", "30%+",
]


def _resample_rule(frequency: str) -> str:
    return "ME" if frequency == "monthly" else "W-FRI"


def periodic_returns(history: pd.DataFrame, years: int, frequency: str = "monthly") -> pd.Series:
    """Percentage returns per month or per week over the trailing window."""
    if history.empty:
        return pd.Series(dtype=float)

    closes = history["Close"].dropna()
    if closes.empty:
        return pd.Series(dtype=float)

    start = closes.index[-1] - dt.timedelta(days=int(365.25 * years))
    window = closes.loc[closes.index >= start]
    if len(window) < 5:
        return pd.Series(dtype=float)

    rule = _resample_rule(frequency)
    try:
        resampled = window.resample(rule).last()
    except ValueError:  # pandas < 2.2 uses "M" instead of "ME"
        resampled = window.resample("M" if frequency == "monthly" else "W-FRI").last()

    return (resampled.pct_change().dropna() * 100)


def distribution_stats(returns: pd.Series, frequency: str = "monthly") -> dict:
    """Mean and standard deviation, reported per period and annualised."""
    if returns.empty:
        return {k: np.nan for k in
                ("mean", "std", "annual_mean", "annual_std", "best", "worst", "hit_rate", "n")}

    periods_per_year = 12 if frequency == "monthly" else 52
    mean = returns.mean()
    std = returns.std()

    return {
        "mean": mean,
        "std": std,
        "annual_mean": ((1 + mean / 100) ** periods_per_year - 1) * 100,
        "annual_std": std * np.sqrt(periods_per_year),
        "best": returns.max(),
        "worst": returns.min(),
        "hit_rate": (returns > 0).mean() * 100,
        "n": int(returns.size),
    }


def bucket_counts(returns: pd.Series) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame()

    frame = pd.DataFrame({"ret": returns.values})
    frame["bucket"] = pd.cut(
        frame["ret"], bins=BUCKET_EDGES, labels=BUCKET_LABELS, include_lowest=True
    )
    summary = (
        frame.groupby("bucket", observed=False)["ret"]
        .agg(count="count", mean="mean")
        .reset_index()
    )
    summary["share"] = summary["count"] / summary["count"].sum() * 100
    return summary


# ----------------------------------------------------------------------------
# 6. Price history with moving averages
# ----------------------------------------------------------------------------

PERIOD_DAYS = {
    "1M": 30, "6M": 182, "1Y": 365, "2Y": 730,
    "3Y": 1095, "5Y": 1826, "7Y": 2557, "10Y": 3653,
}


def with_moving_averages(history: pd.DataFrame, period: str) -> pd.DataFrame:
    """
    Moving averages are computed on the full series and only then sliced, so a
    one-month view still shows a genuine 200-day average instead of a blank line.
    """
    if history.empty:
        return history

    frame = history.copy()
    for window in (50, 100, 200):
        frame[f"DMA{window}"] = frame["Close"].rolling(window).mean()

    days = PERIOD_DAYS.get(period, 365)
    cutoff = frame.index[-1] - dt.timedelta(days=days)
    return frame.loc[frame.index >= cutoff]
