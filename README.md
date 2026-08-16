# Nifty 500 Stock Analyser

A research sheet for any constituent of the Nifty 50 / 100 / 200 / 500. Search a
company, or drill down index → industry → stock, and get a snapshot, peer
valuation, a five-year operating record, returns by holding period, a return
distribution, and a price chart with moving averages.

Built with Streamlit. Data from Yahoo Finance; constituent lists from NSE Indices.

---

## What's on the page

| Section | Contents |
|---|---|
| 01 Snapshot | Price, market cap, shares outstanding, beta, 52-week range |
| 02 Valuation against peers | P/E, forward P/E, P/B, EV/EBITDA, EV/Sales, ROE, dividend yield for the stock and 3–6 same-industry comparables |
| 03 Five-year operating record | Revenue, revenue growth, gross margin, EBITDA, EBITDA margin, net profit, PAT margin, ROE, ROCE, EPS |
| 04 Returns by holding period | 1M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y — absolute and annualised |
| 05 Distribution of returns | Monthly or weekly returns bucketed in 5% bands, with mean and standard deviation |
| 06 Price, moving averages and indicators | Close with 50 / 100 / 200 DMA over 1M to 10Y, plus optional RSI (14) and MACD (12, 26, 9) panes |

---

## Project structure

```
nifty-analytics/
├── app.py                            # the page: layout, widgets, section order
├── requirements.txt                  # dependencies Streamlit Cloud installs
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml                   # colour theme
├── data/
│   └── nifty_universe_fallback.csv   # offline snapshot of the constituent list
└── src/
    ├── universe.py                   # loads Nifty 50/100/200/500 members
    ├── market_data.py                # every Yahoo Finance call, cached
    ├── analytics.py                  # multiples, fundamentals, returns, distributions
    ├── charts.py                     # Plotly figures
    └── theme.py                      # colours, CSS, number formatting
```

The split matters for a reason beyond tidiness: `analytics.py` never imports
Streamlit widgets, so you can test a calculation in a plain Python shell without
launching the app.

### Where the stock list comes from

On first load the app downloads the four official constituent CSVs from NSE
Indices. Those files carry the company name, NSE symbol and NSE's own industry
classification, so the whole universe — including which industry each stock sits
in — is derived rather than typed out by hand. **You never maintain a list of 500
tickers.** When NSE adds or drops a name at the semi-annual review, the app picks
it up within a day.

If NSE is unreachable, it falls back to `data/nifty_universe_fallback.csv`
(271 names) and says so in the sidebar.

---

## Run it on your own machine

You need Python 3.9 or newer.

```bash
# 1. Get the code into a folder and open a terminal there
cd nifty-analytics

# 2. Create an isolated environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch
streamlit run app.py
```

Your browser opens at `http://localhost:8501`. The first stock takes a few
seconds while Yahoo responds; after that it is cached.

`smoke_test.py` renders the entire app with fake data and no network, which is
useful when you change a calculation: `python smoke_test.py`.

---

## Put it on GitHub

### If you have never used git

Easiest route, no commands at all:

1. Sign in at [github.com](https://github.com) and click **New repository**.
2. Name it `nifty-analytics`, choose **Public**, and click **Create repository**.
   Do not tick "Add a README" — you already have one.
3. On the empty repo page click **uploading an existing file**.
4. Drag in `app.py`, `requirements.txt`, `README.md`, `.gitignore`, and the
   `src`, `data` and `.streamlit` folders. GitHub preserves folder structure when
   you drag whole folders from your file manager.
5. Click **Commit changes**.

One caveat: some browsers skip folders whose names begin with a dot, so check
that `.streamlit/config.toml` actually appears. If it did not upload, use
**Add file → Create new file**, type `.streamlit/config.toml` as the filename
(the slash creates the folder), and paste the contents in.

### If you prefer the command line

```bash
cd nifty-analytics
git init
git add .
git commit -m "Nifty 500 stock analyser"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/nifty-analytics.git
git push -u origin main
```

If the push asks for a password, GitHub wants a **personal access token**, not
your account password: Settings → Developer settings → Personal access tokens →
Tokens (classic) → Generate new token, tick `repo`, and paste the token as the
password.

To update the site later, edit the file, then:

```bash
git add .
git commit -m "what you changed"
git push
```

---

## Turn it into a live website

**GitHub Pages will not work here.** Pages serves static HTML only; this app
runs Python on a server every time someone moves a slider. Use Streamlit
Community Cloud instead — it is free, it deploys straight from your repo, and it
redeploys automatically on every push.

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub. Authorise it to read your repositories.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Fill in:
   - Repository: `YOUR-USERNAME/nifty-analytics`
   - Branch: `main`
   - Main file path: `app.py`
4. Optionally set a custom subdomain — this becomes your URL, something like
   `https://nifty-analytics.streamlit.app`.
5. Click **Deploy**. The first build takes two or three minutes while it installs
   the dependencies. Watch the log pane; if a package fails, the error appears
   there.

Your app is now public. Every `git push` to `main` redeploys it.

Community Cloud apps sleep after a stretch with no visitors, and the first
visitor afterwards waits about thirty seconds for it to wake. That is normal on
the free tier.

### Other hosts

| Host | Notes |
|---|---|
| Streamlit Community Cloud | Free, zero config, made for this. Start here. |
| Hugging Face Spaces | Free. Create a Space with the Streamlit SDK and push the same files. |
| Render / Railway | Free tiers exist. Set the start command to `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`. |

---

## Optional: password-protect the site

Community Cloud apps are public by default. To gate yours, add this near the top
of `app.py`, right after `st.set_page_config(...)`:

```python
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    entered = st.text_input("Password", type="password")
    if entered:
        if entered == st.secrets.get("dashboard_password"):
            st.session_state["authenticated"] = True
            return True
        st.error("Incorrect password")
    return False


if not check_password():
    st.stop()
```

Then in Streamlit Cloud open your app's **Settings → Secrets** and add:

```toml
dashboard_password = "whatever-you-choose"
```

Never commit the password to GitHub. `.gitignore` already excludes
`.streamlit/secrets.toml` so a local copy stays off the repo.

---

## Things worth knowing about the data

Yahoo Finance is free, which is the reason to use it and also the reason to
check anything that matters against the company's own filings.

- **Coverage of Indian statements is uneven.** Gross profit in particular is
  often absent; the app derives it from cost of revenue where it can and shows an
  em dash where it cannot. A blank cell means "not reported", never zero.
- **Banks, NBFCs and insurers have no meaningful EV or EBITDA.** Those columns
  stay empty for financial companies by design. Compare them on P/B and ROE.
- **Peer selection is automatic but arguable.** The app picks the closest
  same-industry names by market capitalisation. NSE's industry buckets are broad,
  so use the multiselect to swap in the companies you actually consider
  comparable.
- **Prices are adjusted** for splits, bonuses and dividends, so long-horizon
  returns will not match a raw price chart.
- **Annualised returns for 1M and 6M** scale a short move up to a yearly rate.
  That is arithmetic, not a forecast — read the absolute column for short windows.
- **ROE and ROCE use average balances** across opening and closing positions,
  which is why they differ slightly from screeners that use closing balances.
- **RSI uses Wilder's smoothing**, not a simple rolling average. The two diverge
  by a few points on trending stocks; Wilder's is what broker terminals show.
  Both RSI and MACD are computed on the full price history and then cropped to
  the visible window, so a 1M chart continues the real trend instead of
  restarting from a standing stop.
- **Indicators describe the past.** RSI crossing 70 and MACD crossing its signal
  line are descriptions of where price has been. Evidence that either predicts
  returns on its own is weak, and both generate frequent false signals in
  sideways markets. They are here because they are useful context, not because
  they are a system.

Nothing here is investment advice.

---

## Making changes

- **Add a metric to the peer table** — add a key to the dictionary returned by
  `multiples()` in `src/analytics.py`, then add a matching entry to the format
  dictionary in section 02 of `app.py`.
- **Change the return buckets** — edit `BUCKET_EDGES` and `BUCKET_LABELS` in
  `src/analytics.py`. Keep the two lists the same length, edges being one longer.
- **Change colours or fonts** — everything lives in `COLORS` and `CSS` in
  `src/theme.py`.
- **Add a holding period** — add an entry to `HORIZONS` in `src/analytics.py`.
- **Change the RSI or MACD settings** — edit `RSI_PERIOD` and
  `MACD_FAST` / `MACD_SLOW` / `MACD_SIGNAL` at the top of the indicator block in
  `src/analytics.py`. The pane labels read those constants, so they relabel
  themselves.
- **Add another indicator** — write the calculation in `src/analytics.py`, add
  its column inside `with_indicators()`, then add a pane in `price_chart()` in
  `src/charts.py`. Note that `add_hline` and `add_hrect` must be called *after*
  the pane's first trace, or Plotly drops them.
- **Track a different index** — add its NSE constituent file to `INDEX_FILES` in
  `src/universe.py`; the filenames follow the pattern
  `ind_niftymidcap150list.csv`.
