"""
Nifty 500 Stock Analyser
========================
A single-page research sheet for any constituent of the Nifty 50 / 100 / 200 / 500.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import analytics, charts, market_data, theme, universe as uni

st.set_page_config(
    page_title="Nifty 500 Stock Analyser",
    page_icon="•",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(theme.CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

with st.spinner("Loading the Nifty constituent lists..."):
    UNIVERSE, SOURCE = uni.load_universe()

LABEL_TO_SYMBOL = dict(zip(UNIVERSE["label"], UNIVERSE["symbol"]))


# ---------------------------------------------------------------------------
# Sidebar: index tier -> industry -> stock
# ---------------------------------------------------------------------------

st.sidebar.markdown("### Browse")

tier = st.sidebar.selectbox("Index universe", uni.TIER_ORDER, index=3)
pool = uni.within_tier(UNIVERSE, tier)

industry_options = ["All industries"] + uni.industries_in(pool)
industry = st.sidebar.selectbox("Industry", industry_options, index=0)
if industry != "All industries":
    pool = pool[pool["industry"] == industry]

if pool.empty:
    st.sidebar.warning("No stocks match that combination.")
    st.stop()

dropdown_label = st.sidebar.selectbox(
    f"Stock ({len(pool)} available)", pool["label"].tolist(), index=0
)

st.sidebar.markdown(
    f'<div class="note">Constituents from {SOURCE}.<br>'
    "Prices and financials from Yahoo Finance.</div>",
    unsafe_allow_html=True,
)
if st.sidebar.button("Clear cached data", width="stretch"):
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------------------------
# Search bar (takes priority over the sidebar while it has text in it)
# ---------------------------------------------------------------------------

search_column, hint_column = st.columns([3, 2])
with search_column:
    query = st.text_input(
        "Search",
        placeholder="Search any Nifty 500 company or NSE symbol, e.g. Infosys or INFY",
        label_visibility="collapsed",
    )

selected_symbol = LABEL_TO_SYMBOL[dropdown_label]

if query.strip():
    hits = uni.search(UNIVERSE, query)
    if hits.empty:
        st.warning(
            f"Nothing in the Nifty 500 matches '{query}'. "
            "Try the NSE symbol, or clear the box to browse by industry."
        )
    elif len(hits) == 1:
        selected_symbol = hits.iloc[0]["symbol"]
    else:
        with hint_column:
            picked = st.selectbox(
                "Matches", hits["label"].tolist(), index=0, label_visibility="collapsed"
            )
        selected_symbol = LABEL_TO_SYMBOL[picked]

row = UNIVERSE[UNIVERSE["symbol"] == selected_symbol].iloc[0]
ticker = row["ticker"]


# ---------------------------------------------------------------------------
# Load prices
# ---------------------------------------------------------------------------

with st.spinner(f"Fetching {row['symbol']}..."):
    history = market_data.get_price_history(ticker, period="max")

if history.empty:
    st.error(
        f"Yahoo Finance returned no price history for {ticker}. "
        "The symbol may have been renamed on NSE. Pick another stock, or clear the cache "
        "from the sidebar and retry."
    )
    st.stop()

snap = analytics.snapshot(ticker, history)
as_of = history.index[-1].strftime("%d %b %Y")

st.markdown(
    f"""
    <div class="masthead">
      <div class="eyebrow">{row['tier']} &nbsp;/&nbsp; {row['industry']}</div>
      <div class="company">{row['name']}</div>
      <div class="meta">NSE: {row['symbol']} &nbsp;&middot;&nbsp; {ticker}
      &nbsp;&middot;&nbsp; Close as of {as_of}</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 1. Snapshot tiles
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">01 &nbsp; Snapshot</div>', unsafe_allow_html=True)

change = snap["change_pct"]
tone = "up" if pd.notna(change) and change >= 0 else "down"
change_class = "pos" if pd.notna(change) and change >= 0 else "neg"

tiles = st.columns(4)
with tiles[0]:
    sub = (
        f'<span class="{change_class}">{theme.percent(change, signed=True)}</span> on the day'
        if pd.notna(change) else ""
    )
    st.markdown(theme.tile("Share price", theme.rupees(snap["price"]), sub, tone),
                unsafe_allow_html=True)
with tiles[1]:
    st.markdown(theme.tile("Market capitalisation", theme.crore(snap["market_cap_cr"])),
                unsafe_allow_html=True)
with tiles[2]:
    st.markdown(theme.tile("Shares outstanding",
                           theme.number(snap["shares_cr"], 2, " Cr")),
                unsafe_allow_html=True)
with tiles[3]:
    beta = snap["beta"]
    beta_note = ""
    if beta:
        beta_note = "moves more than the market" if beta > 1 else "moves less than the market"
    st.markdown(theme.tile("Beta", theme.number(beta), beta_note), unsafe_allow_html=True)

if snap["week52_low"] and snap["week52_high"]:
    st.markdown(
        f'<div class="note">52-week range {theme.rupees(snap["week52_low"])} '
        f'&ndash; {theme.rupees(snap["week52_high"])}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 2. Peer comparison of multiples
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">02 &nbsp; Valuation against peers</div>',
            unsafe_allow_html=True)

peer_pool = UNIVERSE[
    (UNIVERSE["industry"] == row["industry"]) & (UNIVERSE["symbol"] != row["symbol"])
]

if peer_pool.empty:
    st.info(f"No other {row['industry']} company in the index to compare against.")
else:
    with st.spinner("Selecting comparable companies..."):
        default_peers = analytics.pick_peers(UNIVERSE, row, count=4)

    chosen_peers = st.multiselect(
        "Comparable companies",
        options=peer_pool["symbol"].tolist(),
        default=[p for p in default_peers if p in set(peer_pool["symbol"])],
        format_func=lambda s: peer_pool.loc[peer_pool["symbol"] == s, "name"].iloc[0],
        max_selections=6,
        help="Defaults to the closest companies by market capitalisation in the same "
             "industry. Swap in whichever names you actually consider comparable.",
    )

    with st.spinner("Pulling peer multiples..."):
        comparison = analytics.comparison_table(
            UNIVERSE, [row["symbol"]] + list(chosen_peers)
        )

    if comparison.empty:
        st.info("Yahoo Finance did not return multiples for this peer set.")
    else:
        st.dataframe(
            comparison.style.format({
                "Price (Rs)": "{:,.2f}",
                "Mkt Cap (Rs Cr)": "{:,.0f}",
                "EV (Rs Cr)": "{:,.0f}",
                "P/E": "{:,.1f}x",
                "Fwd P/E": "{:,.1f}x",
                "P/B": "{:,.2f}x",
                "EV/EBITDA": "{:,.1f}x",
                "EV/Sales": "{:,.2f}x",
                "ROE %": "{:,.1f}%",
                "Div Yield %": "{:,.2f}%",
            }, na_rep=theme.DASH),
            width="stretch",
        )

        multiple_columns = st.columns(3)
        for column, metric in zip(multiple_columns, ["P/E", "EV/EBITDA", "P/B"]):
            with column:
                if metric in comparison.columns and comparison[metric].notna().any():
                    st.plotly_chart(
                        charts.peer_multiple_chart(comparison, metric, row["symbol"]),
                        width="stretch",
                    )

        st.markdown(
            '<div class="note">Banks and insurers report no meaningful EV or EBITDA, '
            "so those columns stay blank for financial companies. Judge them on P/B and "
            "ROE instead.</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# 3. Five-year fundamentals
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">03 &nbsp; Five-year operating record</div>',
            unsafe_allow_html=True)

with st.spinner("Reading annual statements..."):
    fundamentals = analytics.fundamentals(ticker, years=5)

if fundamentals.empty:
    st.info("Yahoo Finance has no annual statements for this company.")
else:
    formats = {
        "Revenue (Rs Cr)": lambda v: theme.number(v, 0),
        "Revenue Growth %": lambda v: theme.percent(v, 1, signed=True),
        "Gross Margin %": lambda v: theme.percent(v, 1),
        "EBITDA (Rs Cr)": lambda v: theme.number(v, 0),
        "EBITDA Margin %": lambda v: theme.percent(v, 1),
        "Net Profit (Rs Cr)": lambda v: theme.number(v, 0),
        "PAT Margin %": lambda v: theme.percent(v, 1),
        "ROE %": lambda v: theme.percent(v, 1),
        "ROCE %": lambda v: theme.percent(v, 1),
        "EPS (Rs)": lambda v: theme.number(v, 2),
    }
    display = pd.DataFrame(
        {metric: fundamentals[metric].map(fmt) for metric, fmt in formats.items()}
    ).T
    display.index.name = "Metric"
    st.dataframe(display, width="stretch")

    st.markdown(
        '<div class="note">Financial years run left to right, oldest first. '
        "Gross margin is derived from cost of revenue where the statement omits gross "
        "profit; ROE and ROCE use average balances across opening and closing "
        "positions.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 4. Returns by holding period
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">04 &nbsp; Returns by holding period</div>',
            unsafe_allow_html=True)

returns = analytics.returns_table(history)

if returns.empty or returns["Absolute %"].isna().all():
    st.info("Not enough price history to measure returns.")
else:
    table_column, chart_column = st.columns([2, 3])
    with table_column:
        st.dataframe(
            returns.style
            .map(lambda v: f"color: {theme.COLORS['positive'] if v >= 0 else theme.COLORS['negative']}"
                 if pd.notna(v) else "color: #999")
            .format("{:+,.2f}%", na_rep=theme.DASH),
            width="stretch",
        )
    with chart_column:
        st.plotly_chart(charts.returns_chart(returns), width="stretch")

    st.markdown(
        '<div class="note">Annualised figures are compound annual growth rates. '
        "For the 1M and 6M rows they simply scale a short move up to a yearly rate, "
        "which is arithmetically correct but not a forecast &mdash; read the absolute "
        "column for those. Prices are adjusted for splits, bonuses and dividends.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 5. Distribution of periodic returns
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">05 &nbsp; Distribution of returns</div>',
            unsafe_allow_html=True)

control_columns = st.columns([1, 1, 3])
with control_columns[0]:
    frequency = st.radio("Frequency", ["monthly", "weekly"], horizontal=True,
                         label_visibility="collapsed")
with control_columns[1]:
    window_label = st.selectbox("Window", ["1Y", "2Y", "3Y", "5Y", "10Y"], index=3,
                                label_visibility="collapsed")

window_years = int(window_label.rstrip("Y"))
periodic = analytics.periodic_returns(history, window_years, frequency)
stats = analytics.distribution_stats(periodic, frequency)

if periodic.empty:
    st.info(f"Not enough history for a {window_label} {frequency} distribution.")
else:
    stat_tiles = st.columns(4)
    with stat_tiles[0]:
        st.markdown(theme.tile(
            f"Mean {frequency} return",
            theme.percent(stats["mean"], 2, signed=True),
            f"{theme.percent(stats['annual_mean'], 1, signed=True)} annualised",
            "up" if stats["mean"] >= 0 else "down",
        ), unsafe_allow_html=True)
    with stat_tiles[1]:
        st.markdown(theme.tile(
            "Standard deviation",
            theme.percent(stats["std"], 2),
            f"{theme.percent(stats['annual_std'], 1)} annualised",
        ), unsafe_allow_html=True)
    with stat_tiles[2]:
        st.markdown(theme.tile(
            "Best / worst period",
            f"{theme.percent(stats['best'], 1, signed=True)}",
            f"worst {theme.percent(stats['worst'], 1, signed=True)}",
        ), unsafe_allow_html=True)
    with stat_tiles[3]:
        st.markdown(theme.tile(
            "Positive periods",
            theme.percent(stats["hit_rate"], 0),
            f"out of {stats['n']} {frequency} observations",
        ), unsafe_allow_html=True)

    buckets = analytics.bucket_counts(periodic)
    st.plotly_chart(
        charts.distribution_chart(buckets, frequency, window_label),
        width="stretch",
    )

    # A newly listed company cannot supply a 10-year window; say what it did supply.
    covered_from = periodic.index[0].strftime("%b %Y")
    covered_to = periodic.index[-1].strftime("%b %Y")
    expected = window_years * (12 if frequency == "monthly" else 52)
    shortfall = (
        " The listing is younger than the window selected, so this is the full history "
        "available." if stats["n"] < expected * 0.9 else ""
    )
    st.markdown(
        f'<div class="note">Covering {covered_from} to {covered_to}, '
        f'{stats["n"]} {frequency} periods.{shortfall}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 6. Price history with moving averages
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">06 &nbsp; Price and moving averages</div>',
            unsafe_allow_html=True)

period = st.radio(
    "Chart period",
    list(analytics.PERIOD_DAYS.keys()),
    index=2,
    horizontal=True,
    label_visibility="collapsed",
)

chart_frame = analytics.with_moving_averages(history, period)
if chart_frame.empty:
    st.info("No price data for that window.")
else:
    st.plotly_chart(charts.price_chart(chart_frame, row["symbol"], period),
                    width="stretch")

    latest = chart_frame.iloc[-1]
    signals = []
    for window in (50, 100, 200):
        value = latest.get(f"DMA{window}")
        if pd.notna(value):
            side = "above" if latest["Close"] > value else "below"
            signals.append(f"{side} its {window} DMA ({theme.rupees(value)})")
    if signals:
        st.markdown(
            f'<div class="note">Trading {", ".join(signals)}.</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-label" style="margin-top:28px">About this data</div>'
    '<div class="note">Figures come from Yahoo Finance and are not audited. '
    "Coverage of Indian annual statements is uneven, so some cells will read as blank "
    "rather than guessed. Nothing here is investment advice.</div>",
    unsafe_allow_html=True,
)
