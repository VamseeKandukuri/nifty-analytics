"""
Visual identity and number formatting.

The look is borrowed from a printed dealing sheet rather than a dashboard
template: paper-toned background, hairline rules instead of drop shadows, and
every figure set in a monospaced face with tabular numerals so decimal points
line up down a column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

COLORS = {
    "ink": "#12171F",
    "paper": "#FBFAF7",
    "rule": "#DFDBD1",
    "grid": "#EDEAE3",
    "muted": "#8C8578",
    "accent": "#1F3A5F",
    "positive": "#0B7A4B",
    "negative": "#B23A32",
    "dma50": "#D08C2E",
    "dma100": "#3E7C6B",
    "dma200": "#7A4A8C",
}

MONO_FONT = "IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, monospace"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
}}
.stApp {{ background: {COLORS['paper']}; }}

h1, h2, h3 {{
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
    letter-spacing: -0.015em;
    color: {COLORS['ink']};
}}

/* Masthead */
.masthead {{
    border-bottom: 2px solid {COLORS['ink']};
    padding-bottom: 10px;
    margin-bottom: 6px;
}}
.masthead .eyebrow {{
    font-family: {MONO_FONT};
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: {COLORS['muted']};
}}
.masthead .company {{
    font-size: 30px;
    font-weight: 600;
    line-height: 1.15;
    margin-top: 2px;
    color: {COLORS['ink']};
}}
.masthead .meta {{
    font-family: {MONO_FONT};
    font-size: 12px;
    color: {COLORS['muted']};
    margin-top: 4px;
}}

/* Ledger tiles: hairline top rule, mono figures, no shadow */
.tile {{
    border-top: 3px solid {COLORS['accent']};
    border-bottom: 1px solid {COLORS['rule']};
    padding: 12px 14px 14px 0;
    height: 100%;
}}
.tile .label {{
    font-family: {MONO_FONT};
    font-size: 10.5px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {COLORS['muted']};
}}
.tile .value {{
    font-family: {MONO_FONT};
    font-variant-numeric: tabular-nums;
    font-size: 25px;
    font-weight: 500;
    color: {COLORS['ink']};
    margin-top: 6px;
    line-height: 1.1;
}}
.tile .sub {{
    font-family: {MONO_FONT};
    font-size: 11.5px;
    color: {COLORS['muted']};
    margin-top: 3px;
}}
.tile.up {{ border-top-color: {COLORS['positive']}; }}
.tile.down {{ border-top-color: {COLORS['negative']}; }}
.pos {{ color: {COLORS['positive']}; }}
.neg {{ color: {COLORS['negative']}; }}

.section-label {{
    font-family: {MONO_FONT};
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: {COLORS['muted']};
    border-top: 1px solid {COLORS['rule']};
    padding-top: 14px;
    margin-top: 8px;
}}
.note {{
    font-family: {MONO_FONT};
    font-size: 11.5px;
    color: {COLORS['muted']};
    line-height: 1.5;
}}

[data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; }}
[data-testid="stSidebar"] {{
    background: #F4F1EA00;
    border-right: 1px solid {COLORS['rule']};
}}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {{
    font-family: {MONO_FONT};
    font-size: 11px !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {COLORS['muted']};
}}
</style>
"""


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

DASH = "\u2014"  # em dash stands in for "not reported"


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))) \
        or (isinstance(value, (int, float)) is False and pd.isna(value))


def rupees(value, decimals: int = 2) -> str:
    if _missing(value):
        return DASH
    return f"Rs {value:,.{decimals}f}"


def crore(value) -> str:
    if _missing(value):
        return DASH
    if abs(value) >= 100_000:
        return f"Rs {value / 100_000:,.2f} L Cr"
    return f"Rs {value:,.0f} Cr"


def number(value, decimals: int = 2, suffix: str = "") -> str:
    if _missing(value):
        return DASH
    return f"{value:,.{decimals}f}{suffix}"


def percent(value, decimals: int = 2, signed: bool = False) -> str:
    if _missing(value):
        return DASH
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:,.{decimals}f}%"


def tile(label: str, value: str, sub: str = "", tone: str = "") -> str:
    tone_class = f" {tone}" if tone in ("up", "down") else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="tile{tone_class}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}</div>"
    )
