"""Plotly figures. Colour and type choices come from src/theme.py."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .analytics import MACD_FAST, MACD_SIGNAL, MACD_SLOW, RSI_PERIOD
from .theme import COLORS, MONO_FONT

RSI_LABEL = str(RSI_PERIOD)
MACD_LABEL = f"{MACD_FAST}, {MACD_SLOW}, {MACD_SIGNAL}"


def _base_layout(fig: go.Figure, height: int = 460) -> go.Figure:
    fig.update_layout(
        height=height,
        template="simple_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=MONO_FONT, size=12, color=COLORS["ink"]),
        margin=dict(l=20, r=20, t=50, b=20),
        hoverlabel=dict(font_family=MONO_FONT, font_size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["rule"], ticks="outside",
                     tickcolor=COLORS["rule"])
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False,
                     linecolor=COLORS["rule"])
    return fig


def distribution_chart(summary: pd.DataFrame, frequency: str, window_label: str) -> go.Figure:
    """Histogram of periodic returns across fixed buckets."""
    colors = [
        COLORS["negative"] if str(bucket).startswith("<") or str(bucket).startswith("-")
        else COLORS["positive"]
        for bucket in summary["bucket"]
    ]

    fig = go.Figure(
        go.Bar(
            x=summary["bucket"].astype(str),
            y=summary["count"],
            marker=dict(color=colors, line=dict(width=0)),
            customdata=summary[["share", "mean"]].values,
            hovertemplate=(
                "<b>%{x}</b><br>Periods: %{y}<br>"
                "Share: %{customdata[0]:.1f}%<br>"
                "Average in bucket: %{customdata[1]:+.2f}%<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=dict(
            text=f"{frequency.capitalize()} return distribution — trailing {window_label}",
            font=dict(size=15),
        ),
        bargap=0.18,
        xaxis_title=f"{frequency.capitalize()} return bucket",
        yaxis_title="Number of periods",
    )
    return _base_layout(fig, height=430)


def price_chart(
    frame: pd.DataFrame,
    name: str,
    period: str,
    show_rsi: bool = False,
    show_macd: bool = False,
) -> go.Figure:
    """
    Price with moving averages, and optionally RSI and MACD stacked beneath it.

    The panes share one x-axis so a date lines up vertically across all three:
    reading an RSI peak against the price bar that produced it is the whole
    point of showing them together rather than in separate figures.
    """
    has_rsi = show_rsi and "RSI" in frame.columns and frame["RSI"].notna().any()
    has_macd = show_macd and "MACD" in frame.columns and frame["MACD"].notna().any()

    heights = [0.58]
    titles = ["Price (Rs)"]
    if has_rsi:
        heights.append(0.21)
        titles.append(f"RSI ({RSI_LABEL})")
    if has_macd:
        heights.append(0.21)
        titles.append("MACD")

    # Give the price pane the whole figure when it is the only one.
    if len(heights) == 1:
        heights = [1.0]
    else:
        total = sum(heights)
        heights = [h / total for h in heights]

    fig = make_subplots(
        rows=len(heights), cols=1,
        shared_xaxes=True,
        vertical_spacing=0.045,
        row_heights=heights,
    )

    # --- Pane 1: price and moving averages ---
    fig.add_trace(go.Scatter(
        x=frame.index, y=frame["Close"], name="Close",
        line=dict(color=COLORS["accent"], width=2),
        hovertemplate="Rs %{y:,.2f}<extra>Close</extra>",
    ), row=1, col=1)

    dma_styles = {
        "DMA50": (COLORS["dma50"], "50 DMA"),
        "DMA100": (COLORS["dma100"], "100 DMA"),
        "DMA200": (COLORS["dma200"], "200 DMA"),
    }
    for column, (color, label) in dma_styles.items():
        if column in frame.columns and frame[column].notna().any():
            fig.add_trace(go.Scatter(
                x=frame.index, y=frame[column], name=label,
                line=dict(color=color, width=1.4),
                hovertemplate="Rs %{y:,.2f}<extra>" + label + "</extra>",
            ), row=1, col=1)

    row = 1

    # --- Pane 2: RSI ---
    if has_rsi:
        row += 1
        fig.add_trace(go.Scatter(
            x=frame.index, y=frame["RSI"], name="RSI",
            line=dict(color=COLORS["dma100"], width=1.6),
            hovertemplate="%{y:.1f}<extra>RSI</extra>",
        ), row=row, col=1)

        # These have to come after the trace. Plotly's add_hline and add_hrect
        # default to exclude_empty_subplots=True and will silently skip a row
        # that has nothing plotted in it yet.
        fig.add_hrect(y0=70, y1=100, row=row, col=1, layer="below",
                      fillcolor=COLORS["negative"], opacity=0.06, line_width=0,
                      exclude_empty_subplots=False)
        fig.add_hrect(y0=0, y1=30, row=row, col=1, layer="below",
                      fillcolor=COLORS["positive"], opacity=0.06, line_width=0,
                      exclude_empty_subplots=False)
        for level in (70, 50, 30):
            fig.add_hline(y=level, row=row, col=1, layer="below", line_width=1,
                          line_dash="dot", line_color=COLORS["rule"],
                          exclude_empty_subplots=False)

        fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=row, col=1)

    # --- Pane 3: MACD ---
    if has_macd:
        row += 1
        histogram = frame["MACD_HIST"]
        fig.add_trace(go.Bar(
            x=frame.index, y=histogram, name="Histogram",
            marker=dict(
                color=[COLORS["positive"] if v >= 0 else COLORS["negative"]
                       for v in histogram.fillna(0)],
                line=dict(width=0),
            ),
            opacity=0.45,
            hovertemplate="%{y:,.2f}<extra>Histogram</extra>",
        ), row=row, col=1)

        fig.add_trace(go.Scatter(
            x=frame.index, y=frame["MACD"], name="MACD",
            line=dict(color=COLORS["accent"], width=1.6),
            hovertemplate="%{y:,.2f}<extra>MACD</extra>",
        ), row=row, col=1)
        fig.add_trace(go.Scatter(
            x=frame.index, y=frame["MACD_SIGNAL"], name="Signal",
            line=dict(color=COLORS["dma50"], width=1.4, dash="dot"),
            hovertemplate="%{y:,.2f}<extra>Signal</extra>",
        ), row=row, col=1)

        fig.add_hline(y=0, row=row, col=1, layer="below", line_width=1,
                      line_color=COLORS["rule"], exclude_empty_subplots=False)

    for index, title in enumerate(titles, start=1):
        fig.update_yaxes(title_text=title, title_font=dict(size=11), row=index, col=1)

    fig.update_layout(
        title=dict(text=f"{name} — {period} price history", font=dict(size=15)),
        hovermode="x unified",
        barmode="relative",
    )

    height = 480 + (200 if has_rsi else 0) + (200 if has_macd else 0)
    fig = _base_layout(fig, height=height)
    fig.update_xaxes(hoverformat="%d %b %Y")
    return fig


def returns_chart(returns: pd.DataFrame) -> go.Figure:
    """Absolute and annualised return side by side for each holding period."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=returns.index.astype(str), y=returns["Absolute %"], name="Absolute",
        marker=dict(color=COLORS["accent"], line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Absolute: %{y:+.2f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=returns.index.astype(str), y=returns["Annualised (CAGR) %"], name="Annualised",
        marker=dict(color=COLORS["dma50"], line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Annualised: %{y:+.2f}%<extra></extra>",
    ))

    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08,
                      yaxis_title="Return (%)")
    fig = _base_layout(fig, height=300)
    fig.add_hline(y=0, line_width=1, line_color=COLORS["rule"])
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    return fig


def peer_multiple_chart(table: pd.DataFrame, metric: str, highlight: str) -> go.Figure:
    """Small bar chart putting one multiple side by side across the peer set."""
    data = table[metric].dropna()
    if data.empty:
        return go.Figure()

    colors = [COLORS["accent"] if idx == highlight else COLORS["muted"] for idx in data.index]

    fig = go.Figure(
        go.Bar(
            x=data.index.astype(str), y=data.values,
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{v:,.1f}" for v in data.values],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>" + metric + ": %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(title=dict(text=metric, font=dict(size=13)), bargap=0.35)
    fig = _base_layout(fig, height=260)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
    return fig
