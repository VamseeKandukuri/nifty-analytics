"""Plotly figures. Colour and type choices come from src/theme.py."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import COLORS, MONO_FONT


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


def price_chart(frame: pd.DataFrame, name: str, period: str) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=frame.index, y=frame["Close"], name="Close",
        line=dict(color=COLORS["accent"], width=2),
        hovertemplate="%{x|%d %b %Y}<br>Rs %{y:,.2f}<extra>Close</extra>",
    ))

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
                hovertemplate="%{x|%d %b %Y}<br>Rs %{y:,.2f}<extra>" + label + "</extra>",
            ))

    fig.update_layout(
        title=dict(text=f"{name} — {period} price history", font=dict(size=15)),
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title="Price (Rs)",
    )
    return _base_layout(fig, height=480)


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
