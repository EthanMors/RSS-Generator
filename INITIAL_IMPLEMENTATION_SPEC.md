# Reddit Stock Sentiment Scraper — Implementation Specification

**For:** Claude Haiku  
**Purpose:** Complete, unambiguous build instructions. Every decision is made for you. Do not interpret — implement exactly as written.

---

## 1. What You Are Building

A Python application that:
1. Polls a Reddit subreddit every 15 minutes using the public Reddit JSON API (no OAuth)
2. Extracts stock ticker symbols from post titles and body text
3. Runs each post's text through the Gemini AI API to produce a sentiment score
4. Stores results in a local SQLite database organized by date
5. Exposes a Streamlit web dashboard for visual inspection

---

## 2. Final File & Folder Structure

Create every file listed below. Do not create any other files.

```
RSS-Generator/
├── .env                  ← User fills this in; you create .env.example
├── .env.example          ← Template showing required variables
├── requirements.txt      ← All Python dependencies
├── config.py             ← Loads .env, builds USER_AGENT string
├── scraper.py            ← Fetches posts from Reddit JSON API
├── parser.py             ← Extracts ticker symbols from text
├── sentiment.py          ← Calls Gemini API, returns score + label
├── database.py           ← All SQLite read/write operations
├── scheduler.py          ← APScheduler loop, orchestrates pipeline
├── app.py                ← Streamlit dashboard
└── main.py               ← Entry point: starts scheduler
```

`.env` is **not created by you**. You create `.env.example` only.

---

## 3. Environment Variables

### 3a. `.env.example` — create this file exactly

```
# Your Reddit username (used in the API User-Agent string)
REDDIT_USERNAME=your_reddit_username_here

# The subreddit to scrape, no r/ prefix
SUBREDDIT=wallstreetbets

# Your Google Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3b. Variable Usage Reference

| Variable | Type | Used In | Purpose |
|---|---|---|---|
| `REDDIT_USERNAME` | string | `config.py` | Embedded in User-Agent header |
| `SUBREDDIT` | string | `config.py`, `scraper.py` | Which subreddit to scrape |
| `GEMINI_API_KEY` | string | `sentiment.py` | Authenticates Gemini API calls |

---

## 4. `requirements.txt`

Write this file exactly as shown. No version pinning — use bare package names so pip resolves latest stable:

```
requests
python-dotenv
google-generativeai
apscheduler
streamlit
pandas
plotly
```

---

## 5. `config.py` — Configuration Loader

**Purpose:** Load `.env`, validate all required vars exist, expose constants.

```python
import os
from dotenv import load_dotenv

load_dotenv()

REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
SUBREDDIT = os.getenv("SUBREDDIT")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validate — raise immediately on startup if any var is missing
for var_name, var_value in [
    ("REDDIT_USERNAME", REDDIT_USERNAME),
    ("SUBREDDIT", SUBREDDIT),
    ("GEMINI_API_KEY", GEMINI_API_KEY),
]:
    if not var_value:
        raise EnvironmentError(f"Missing required environment variable: {var_name}")

# Reddit API User-Agent
# Format: python:<app_id>:<version> (by /u/<reddit_username>)
APP_ID = "RedditStockSentimentScraper"
APP_VERSION = "v1.0.0"
USER_AGENT = f"python:{APP_ID}:{APP_VERSION} (by /u/{REDDIT_USERNAME})"

# Reddit fetch settings
REDDIT_POST_LIMIT = 100        # Max posts per request (Reddit max is 100)
REDDIT_BASE_URL = "https://www.reddit.com"

# SQLite database file path (same directory as this script)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reddit_stocks.db")

# Scheduler interval in minutes
POLL_INTERVAL_MINUTES = 15
```

**Rules:**
- Do not add any other logic to this file
- Import `config` in all other modules using `import config`

---

## 6. `database.py` — SQLite Operations

**Purpose:** Create tables, insert records, query records. All database code lives here.

### 6a. Import Block

```python
import sqlite3
import config
```

### 6b. Table Schemas — Create All Three Tables

Call `initialize_db()` once at startup. It creates all tables if they do not exist.

#### Table 1: `posts`

Stores every Reddit post fetched. `post_id` is Reddit's native post ID (the alphanumeric string, e.g., `"1abc23"`). The `UNIQUE` constraint on `post_id` prevents duplicates across poll cycles.

```sql
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     TEXT    UNIQUE NOT NULL,
    subreddit   TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    selftext    TEXT    DEFAULT '',
    author      TEXT    DEFAULT '[deleted]',
    score       INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    created_utc REAL    NOT NULL,
    url         TEXT    DEFAULT '',
    permalink   TEXT    DEFAULT '',
    fetched_at  TEXT    NOT NULL,
    date        TEXT    NOT NULL
)
```

Column definitions:
- `post_id` — Reddit's `id` field from the JSON response
- `created_utc` — Reddit's `created_utc` field (Unix timestamp, float)
- `fetched_at` — ISO 8601 datetime string when your code fetched it: `"2025-04-30T14:32:00"`
- `date` — `"YYYY-MM-DD"` string derived from `created_utc` using `datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%d")`

#### Table 2: `ticker_mentions`

One row per ticker per post. If a post mentions AAPL twice, that still produces one row with `mention_count=2`.

```sql
CREATE TABLE IF NOT EXISTS ticker_mentions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT    NOT NULL,
    post_id          TEXT    NOT NULL,
    mention_count    INTEGER NOT NULL DEFAULT 1,
    sentiment_score  REAL    NOT NULL,
    sentiment_label  TEXT    NOT NULL,
    timestamp        TEXT    NOT NULL,
    date             TEXT    NOT NULL,
    subreddit        TEXT    NOT NULL
)
```

Column definitions:
- `ticker` — Uppercase ticker symbol without `$`, e.g., `"AAPL"`
- `post_id` — The Reddit post ID (links logically to `posts.post_id`)
- `mention_count` — How many times this ticker appeared in `title + selftext` combined
- `sentiment_score` — Float from `-1.0` (most negative) to `1.0` (most positive). Provided by Gemini.
- `sentiment_label` — Exactly one of three strings: `"positive"`, `"negative"`, `"neutral"`
- `timestamp` — ISO 8601 datetime string when Gemini analysis was run
- `date` — `"YYYY-MM-DD"` string matching the post's `date` value

#### Table 3: `daily_summary`

Pre-aggregated one row per ticker per day per subreddit. Recalculated each time new data arrives for that day.

```sql
CREATE TABLE IF NOT EXISTS daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    ticker          TEXT    NOT NULL,
    total_mentions  INTEGER NOT NULL DEFAULT 0,
    avg_sentiment   REAL    NOT NULL DEFAULT 0.0,
    min_sentiment   REAL    NOT NULL DEFAULT 0.0,
    max_sentiment   REAL    NOT NULL DEFAULT 0.0,
    post_count      INTEGER NOT NULL DEFAULT 0,
    subreddit       TEXT    NOT NULL,
    last_updated    TEXT    NOT NULL,
    UNIQUE(date, ticker, subreddit)
)
```

### 6c. Function Signatures and Exact Behavior

#### `initialize_db()`

```python
def initialize_db():
```

- Opens a connection to `config.DB_PATH`
- Executes all three `CREATE TABLE IF NOT EXISTS` statements above
- Calls `conn.commit()`
- Closes connection
- Prints: `"[DB] Database initialized at {config.DB_PATH}"`

---

#### `post_exists(post_id: str) -> bool`

```python
def post_exists(post_id: str) -> bool:
```

- Returns `True` if a row with that `post_id` exists in the `posts` table
- Returns `False` otherwise
- Used by the scheduler to skip already-processed posts

---

#### `insert_post(post: dict) -> None`

```python
def insert_post(post: dict) -> None:
```

`post` dict has these exact keys (matches Reddit API field names plus extras you add):

```python
{
    "post_id":      str,   # Reddit id field
    "subreddit":    str,
    "title":        str,
    "selftext":     str,
    "author":       str,
    "score":        int,
    "num_comments": int,
    "created_utc":  float,
    "url":          str,
    "permalink":    str,
    "fetched_at":   str,   # ISO datetime string
    "date":         str,   # YYYY-MM-DD
}
```

Use `INSERT OR IGNORE` so duplicate `post_id` values silently fail:

```sql
INSERT OR IGNORE INTO posts (post_id, subreddit, title, selftext, author, score,
    num_comments, created_utc, url, permalink, fetched_at, date)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

---

#### `insert_ticker_mention(mention: dict) -> None`

```python
def insert_ticker_mention(mention: dict) -> None:
```

`mention` dict:

```python
{
    "ticker":          str,
    "post_id":         str,
    "mention_count":   int,
    "sentiment_score": float,
    "sentiment_label": str,
    "timestamp":       str,   # ISO datetime string
    "date":            str,   # YYYY-MM-DD
    "subreddit":       str,
}
```

Use plain `INSERT INTO ticker_mentions`:

```sql
INSERT INTO ticker_mentions (ticker, post_id, mention_count, sentiment_score,
    sentiment_label, timestamp, date, subreddit)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

---

#### `upsert_daily_summary(date: str, ticker: str, subreddit: str) -> None`

```python
def upsert_daily_summary(date: str, ticker: str, subreddit: str) -> None:
```

Recalculates aggregates for this `(date, ticker, subreddit)` combination by querying `ticker_mentions`, then writes to `daily_summary` using `INSERT OR REPLACE`:

Step 1 — Query:
```sql
SELECT COUNT(*) as post_count,
       SUM(mention_count) as total_mentions,
       AVG(sentiment_score) as avg_sentiment,
       MIN(sentiment_score) as min_sentiment,
       MAX(sentiment_score) as max_sentiment
FROM ticker_mentions
WHERE date = ? AND ticker = ? AND subreddit = ?
```

Step 2 — Insert or replace:
```sql
INSERT OR REPLACE INTO daily_summary
    (date, ticker, total_mentions, avg_sentiment, min_sentiment, max_sentiment,
     post_count, subreddit, last_updated)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
```

`last_updated` = current UTC datetime as ISO string.

---

#### `get_daily_summary(date: str, subreddit: str) -> list[dict]`

```python
def get_daily_summary(date: str, subreddit: str) -> list[dict]:
```

Returns all rows from `daily_summary` for this date and subreddit, sorted by `total_mentions DESC`.

```sql
SELECT * FROM daily_summary
WHERE date = ? AND subreddit = ?
ORDER BY total_mentions DESC
```

Return a list of dicts. Each dict has the column names as keys.

---

#### `get_recent_ticker_mentions(subreddit: str, limit: int = 200) -> list[dict]`

```python
def get_recent_ticker_mentions(subreddit: str, limit: int = 200) -> list[dict]:
```

Returns the most recent rows from `ticker_mentions` for a subreddit:

```sql
SELECT * FROM ticker_mentions
WHERE subreddit = ?
ORDER BY timestamp DESC
LIMIT ?
```

Return a list of dicts.

---

#### `get_sentiment_over_time(ticker: str, subreddit: str, days: int = 7) -> list[dict]`

```python
def get_sentiment_over_time(ticker: str, subreddit: str, days: int = 7) -> list[dict]:
```

Returns `daily_summary` rows for a specific ticker over the last N days:

```sql
SELECT date, avg_sentiment, total_mentions
FROM daily_summary
WHERE ticker = ? AND subreddit = ?
ORDER BY date ASC
LIMIT ?
```

Return a list of dicts.

---

## 7. `scraper.py` — Reddit API Fetcher

**Purpose:** Make a single HTTP GET request to Reddit. Return a list of post dicts.

### 7a. Import Block

```python
import requests
from datetime import datetime, timezone
import config
```

### 7b. `fetch_posts(subreddit: str, limit: int = 100) -> list[dict]`

```python
def fetch_posts(subreddit: str, limit: int = 100) -> list[dict]:
```

**URL:**
```
https://www.reddit.com/r/{subreddit}/new.json?limit={limit}
```

**Headers:**
```python
headers = {
    "User-Agent": config.USER_AGENT
}
```

No other headers are required.

**HTTP Call:**

```python
response = requests.get(url, headers=headers, timeout=10)
response.raise_for_status()
data = response.json()
```

**Parse Response:**

The Reddit JSON structure is:
```
data["data"]["children"]  →  list of post wrappers
each wrapper["data"]      →  the actual post fields
```

For each child in `data["data"]["children"]`:

```python
post_data = child["data"]
```

Extract these fields:

| Dict key | Reddit source field | Fallback if None |
|---|---|---|
| `post_id` | `post_data["id"]` | — (required, skip if missing) |
| `subreddit` | `post_data["subreddit"]` | `subreddit` param |
| `title` | `post_data["title"]` | — (required, skip if missing) |
| `selftext` | `post_data["selftext"]` | `""` |
| `author` | `post_data["author"]` | `"[deleted]"` |
| `score` | `post_data["score"]` | `0` |
| `num_comments` | `post_data["num_comments"]` | `0` |
| `created_utc` | `post_data["created_utc"]` | — (required, skip if missing) |
| `url` | `post_data["url"]` | `""` |
| `permalink` | `post_data["permalink"]` | `""` |

Add two computed fields:

```python
post["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
post["date"] = datetime.utcfromtimestamp(post_data["created_utc"]).strftime("%Y-%m-%d")
```

**Error Handling:**

Wrap the entire function body in a `try/except`. On any exception:
- Print: `"[SCRAPER] Error fetching posts: {e}"`
- Return `[]` (empty list)

**Return:** List of post dicts. Return `[]` if no posts found.

---

## 8. `parser.py` — Ticker Extractor

**Purpose:** Given a string of text, return a dict of `{ticker: count}` for all stock tickers found.

### 8a. Import Block

```python
import re
```

### 8b. Ticker Detection Logic

Use two detection methods combined:

**Method 1 — Dollar-sign prefix (primary):**

Pattern: `\$([A-Z]{1,5})\b`

This matches `$AAPL`, `$TSLA`, `$BRK` etc. Capture group 1 is the ticker without the `$`.

**Method 2 — Known tickers list (secondary):**

Match standalone ALL-CAPS words of 1–5 letters that appear in a hardcoded set.

Define this exact set at the top of `parser.py`:

```python
KNOWN_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM",
    "V", "JNJ", "UNH", "XOM", "WMT", "PG", "MA", "HD", "CVX", "MRK", "ABBV",
    "LLY", "PEP", "KO", "AVGO", "COST", "MCD", "TMO", "ACN", "NKE", "DHR",
    "WFC", "BAC", "CRM", "AMD", "INTC", "QCOM", "TXN", "LIN", "UNP", "RTX",
    "HON", "PM", "T", "IBM", "GE", "CAT", "BA", "GS", "MS", "BLK", "SPGI",
    "SCHW", "AXP", "USB", "C", "PNC", "TFC", "COF", "AIG", "CB", "CME",
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "GLD", "SLV", "TLT", "HYG",
    "GME", "AMC", "BBBY", "NOK", "BB", "PLTR", "RBLX", "HOOD", "RIVN", "LCID",
    "COIN", "MSTR", "RIOT", "MARA", "HUT", "BITF", "CLSK",
    "NFLX", "DIS", "UBER", "LYFT", "SNAP", "TWTR", "PINS", "SPOT", "SQ", "PYPL",
    "SHOP", "ROKU", "ZM", "DOCU", "CRWD", "NET", "DDOG", "SNOW", "ABNB",
    "F", "GM", "TM", "STLA", "HMC", "RACE", "NKLA", "WKHS",
    "PFE", "MRNA", "BNTX", "JNJ", "AZN", "GILD", "REGN", "BIIB", "VRTX",
    "XOM", "CVX", "COP", "SLB", "HAL", "BKR", "MPC", "VLO", "PSX",
    "WMT", "TGT", "COST", "AMZN", "EBAY", "ETSY", "W",
    "BTC", "ETH", "BRK"
}
```

**Method 2 pattern:** `\b([A-Z]{1,5})\b`

Only keep matches from this pattern if they are in `KNOWN_TICKERS`.

### 8c. `extract_tickers(text: str) -> dict[str, int]`

```python
def extract_tickers(text: str) -> dict[str, int]:
```

**Steps:**

1. Combine results from both methods into one dict with ticker → total count
2. For Method 1: find all `\$([A-Z]{1,5})\b` matches, strip the `$`, count occurrences
3. For Method 2: find all `\b([A-Z]{1,5})\b` matches, filter to only `KNOWN_TICKERS`, count occurrences
4. Merge: if ticker appears in both, sum the counts
5. Exclude these non-ticker false positives from final results (remove if found): `{"A", "I", "AT", "BE", "BY", "DO", "GO", "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OK", "ON", "OR", "SO", "TO", "UP", "US", "WE"}`
6. Return the merged dict

**Example:** `"I like $AAPL and TSLA is moving. Buy AAPL now"` → `{"AAPL": 3, "TSLA": 1}`

**Edge cases:**
- If `text` is `None` or empty string, return `{}`
- The function converts `text` to uppercase before searching

---

## 9. `sentiment.py` — Gemini Sentiment Analysis

**Purpose:** Given post text (title + body), call the Gemini CLI and return a sentiment score and label.

### 9a. Import Block

```python
import subprocess
import json
import re
```

### 9b. Gemini CLI Usage

The function executes the `gemini` command via `subprocess`.

### 9c. `analyze_sentiment(title: str, body: str, ticker: str) -> dict`

```python
def analyze_sentiment(title: str, body: str, ticker: str) -> dict:
```

**Returns:**
```python
{
    "sentiment_score": float,   # -1.0 to 1.0
    "sentiment_label": str,     # "positive", "negative", or "neutral"
}
```

**Prompt — use this exact text:**

```python
prompt = f"""You are a financial sentiment analyzer for Reddit posts about stocks.

Analyze the sentiment of this Reddit post specifically regarding the stock ticker {ticker}.

Post Title: {title}

Post Body: {body}

Respond ONLY with a JSON object in this exact format, nothing else:
{{"sentiment_score": <float between -1.0 and 1.0>, "sentiment_label": "<positive|negative|neutral>"}}

Rules:
- sentiment_score must be a number between -1.0 (most negative) and 1.0 (most positive)
- sentiment_label must be exactly one of: positive, negative, neutral
- Use neutral (score near 0.0) for factual/informational posts
- Base the sentiment on how the post author feels about this stock
- If the ticker is not directly discussed, return neutral with score 0.0"""
```

**API Call:**

```python
response = model.generate_content(prompt)
response_text = response.text.strip()
```

**Parse Response:**

The response is expected to be a JSON string. Parse it:

```python
# Remove markdown code fences if present (```json ... ```)
response_text = re.sub(r"```(?:json)?\s*", "", response_text).strip()
result = json.loads(response_text)
```

Validate:
- `sentiment_score` must be a number; clamp it to `[-1.0, 1.0]` using `max(-1.0, min(1.0, float(result["sentiment_score"])))`
- `sentiment_label` must be one of `["positive", "negative", "neutral"]`; if not, derive it from score: score > 0.1 → `"positive"`, score < -0.1 → `"negative"`, else `"neutral"`

**Error Handling:**

Wrap everything in `try/except`. On any exception:
- Print: `"[SENTIMENT] Error analyzing sentiment for {ticker}: {e}"`
- Return: `{"sentiment_score": 0.0, "sentiment_label": "neutral"}`

---

## 10. `scheduler.py` — Pipeline Orchestrator

**Purpose:** The APScheduler polling loop. Each 15-minute run calls scraper → parser → sentiment → database.

### 10a. Import Block

```python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import config
import database
import scraper
import parser
import sentiment
```

### 10b. `run_pipeline() -> None`

```python
def run_pipeline() -> None:
```

This function runs the full data pipeline for one poll cycle. Print status messages at each step.

**Step-by-step implementation:**

```
Step 1: Print start message
    Print: "[PIPELINE] Starting poll at {current UTC time ISO string}"

Step 2: Fetch posts
    posts = scraper.fetch_posts(config.SUBREDDIT, limit=config.REDDIT_POST_LIMIT)
    Print: "[PIPELINE] Fetched {len(posts)} posts from r/{config.SUBREDDIT}"

Step 3: For each post in posts:

    3a. Skip if already processed:
        if database.post_exists(post["post_id"]):
            continue

    3b. Insert post into database:
        database.insert_post(post)

    3c. Combine title and body text:
        combined_text = post["title"] + " " + post.get("selftext", "")

    3d. Extract tickers:
        tickers = parser.extract_tickers(combined_text)
        if not tickers:
            continue   ← skip posts with no tickers

    3e. For each (ticker, count) in tickers.items():

        3e-i. Run sentiment analysis:
            sentiment_result = sentiment.analyze_sentiment(
                title=post["title"],
                body=post.get("selftext", ""),
                ticker=ticker
            )

        3e-ii. Build mention dict and insert:
            mention = {
                "ticker":          ticker,
                "post_id":         post["post_id"],
                "mention_count":   count,
                "sentiment_score": sentiment_result["sentiment_score"],
                "sentiment_label": sentiment_result["sentiment_label"],
                "timestamp":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "date":            post["date"],
                "subreddit":       config.SUBREDDIT,
            }
            database.insert_ticker_mention(mention)

        3e-iii. Update daily summary:
            database.upsert_daily_summary(
                date=post["date"],
                ticker=ticker,
                subreddit=config.SUBREDDIT
            )

Step 4: Print completion message
    Print: "[PIPELINE] Poll complete at {current UTC time ISO string}"
```

**Error Handling:**

Wrap the entire function body in `try/except`. On any exception:
- Print: `"[PIPELINE] ERROR in pipeline: {e}"`
- Do NOT re-raise — let the scheduler continue to the next interval

### 10c. `start_scheduler() -> None`

```python
def start_scheduler() -> None:
```

```python
def start_scheduler() -> None:
    print(f"[SCHEDULER] Initializing database...")
    database.initialize_db()

    print(f"[SCHEDULER] Running initial pipeline immediately...")
    run_pipeline()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=config.POLL_INTERVAL_MINUTES),
        id="reddit_poll",
        name="Reddit Stock Scraper",
        replace_existing=True,
    )

    print(f"[SCHEDULER] Scheduler started. Polling every {config.POLL_INTERVAL_MINUTES} minutes.")
    print(f"[SCHEDULER] Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[SCHEDULER] Shutdown requested. Stopping.")
        scheduler.shutdown()
```

---

## 11. `main.py` — Entry Point

```python
import scheduler

if __name__ == "__main__":
    scheduler.start_scheduler()
```

That is the entire file. Nothing else.

---

## 12. `app.py` — Streamlit Dashboard

**Purpose:** Visual dashboard for reviewing pipeline results. Reads from SQLite. Does NOT run the pipeline.

### 12a. Import Block

```python
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import database
import config
```

### 12b. Page Configuration

First line after imports, before any other Streamlit calls:

```python
st.set_page_config(
    page_title="Reddit Stock Sentiment",
    page_icon="📈",
    layout="wide"
)
```

### 12c. Initialize Database

```python
database.initialize_db()
```

### 12d. Title and Subheader

```python
st.title("📈 Reddit Stock Sentiment Dashboard")
st.subheader(f"Tracking r/{config.SUBREDDIT}")
```

### 12e. Date Selector Sidebar

```python
st.sidebar.header("Filters")

today = datetime.utcnow().date()
selected_date = st.sidebar.date_input(
    "Select Date",
    value=today,
    min_value=today - timedelta(days=30),
    max_value=today,
)
selected_date_str = selected_date.strftime("%Y-%m-%d")
```

### 12f. Load Data

```python
daily_data = database.get_daily_summary(selected_date_str, config.SUBREDDIT)
recent_mentions = database.get_recent_ticker_mentions(config.SUBREDDIT, limit=500)

df_daily = pd.DataFrame(daily_data) if daily_data else pd.DataFrame()
df_mentions = pd.DataFrame(recent_mentions) if recent_mentions else pd.DataFrame()
```

### 12g. Metrics Row — 3 columns

```python
col1, col2, col3 = st.columns(3)
```

**col1 — Total Unique Tickers Today:**
```python
with col1:
    count = len(df_daily) if not df_daily.empty else 0
    st.metric("Unique Tickers Today", count)
```

**col2 — Most Mentioned Ticker:**
```python
with col2:
    if not df_daily.empty:
        top = df_daily.iloc[0]
        st.metric("Most Mentioned", top["ticker"], f"{int(top['total_mentions'])} mentions")
    else:
        st.metric("Most Mentioned", "—")
```

**col3 — Average Sentiment Today:**
```python
with col3:
    if not df_daily.empty:
        avg = df_daily["avg_sentiment"].mean()
        label = "Positive" if avg > 0.1 else ("Negative" if avg < -0.1 else "Neutral")
        st.metric("Avg Sentiment Today", f"{avg:.3f}", label)
    else:
        st.metric("Avg Sentiment Today", "—")
```

### 12h. Bar Chart — Top 10 Tickers by Mentions

```python
st.subheader(f"Top Tickers on {selected_date_str}")

if not df_daily.empty:
    top10 = df_daily.head(10).copy()
    fig_bar = px.bar(
        top10,
        x="ticker",
        y="total_mentions",
        color="avg_sentiment",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        range_color=[-1, 1],
        labels={"total_mentions": "Total Mentions", "ticker": "Ticker", "avg_sentiment": "Avg Sentiment"},
        title="Top 10 Tickers by Mention Count (color = sentiment)",
    )
    fig_bar.update_layout(height=400)
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("No data for this date. Make sure the scraper is running.")
```

### 12i. Sentiment Over Time — Line Chart

```python
st.subheader("Sentiment Over Time")

if not df_daily.empty:
    ticker_options = df_daily["ticker"].tolist()
    selected_ticker = st.selectbox("Select Ticker", ticker_options)

    history = database.get_sentiment_over_time(selected_ticker, config.SUBREDDIT, days=7)
    if history:
        df_history = pd.DataFrame(history)
        fig_line = px.line(
            df_history,
            x="date",
            y="avg_sentiment",
            title=f"{selected_ticker} Sentiment — Last 7 Days",
            labels={"avg_sentiment": "Avg Sentiment", "date": "Date"},
            markers=True,
        )
        fig_line.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_line.update_layout(height=350, yaxis_range=[-1, 1])
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info(f"No historical data for {selected_ticker} yet.")
else:
    st.info("No ticker data available.")
```

### 12j. Raw Data Table

```python
st.subheader("Recent Ticker Mentions (last 500)")

if not df_mentions.empty:
    display_cols = ["ticker", "mention_count", "sentiment_score", "sentiment_label", "date", "post_id"]
    available = [c for c in display_cols if c in df_mentions.columns]
    st.dataframe(df_mentions[available], use_container_width=True, height=400)
else:
    st.info("No mention data yet.")
```

### 12k. Refresh Button

```python
st.divider()
if st.button("🔄 Refresh Dashboard"):
    st.rerun()

st.caption(f"Data from r/{config.SUBREDDIT} | Scraper runs every {config.POLL_INTERVAL_MINUTES} minutes | DB: {config.DB_PATH}")
```

---

## 13. How to Run

### 13a. Setup Commands (run once)

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in values:
```bash
cp .env.example .env
```

### 13b. Start the Scraper

```bash
python main.py
```

Output will show `[PIPELINE]` and `[SCHEDULER]` prefixed log lines every 15 minutes.

### 13c. Start the Dashboard (separate terminal)

```bash
streamlit run app.py
```

Opens in browser at `http://localhost:8501`

---

## 14. Error Handling Rules

Apply these rules consistently across all modules:

1. **`scraper.py`**: Any `requests` exception → print error, return `[]`
2. **`sentiment.py`**: Any Gemini/JSON exception → print error, return neutral `{score: 0.0, label: "neutral"}`
3. **`database.py`**: Let SQLite exceptions propagate (they indicate a bug, not expected failure)
4. **`scheduler.py` `run_pipeline()`**: Catch all exceptions → print error, do not re-raise
5. Never use bare `except:` — always use `except Exception as e:`

---

## 15. Print/Logging Conventions

All print statements follow the format: `"[MODULE_NAME] message"` where `MODULE_NAME` is uppercase.

| Module | Prefix |
|---|---|
| `database.py` | `[DB]` |
| `scraper.py` | `[SCRAPER]` |
| `parser.py` | `[PARSER]` (only for errors) |
| `sentiment.py` | `[SENTIMENT]` |
| `scheduler.py` | `[SCHEDULER]` |
| `main.py` | `[MAIN]` |

---

## 16. Critical Constraints

1. **Do NOT use OAuth for Reddit.** Only use the public `.json` endpoint with a `User-Agent` header.
2. **Do NOT store duplicate posts.** Use `post_exists()` before inserting. The `INSERT OR IGNORE` handles race conditions.
3. **Do NOT call Gemini for posts with no tickers.** Skip immediately after `extract_tickers()` returns `{}`.
4. **The database file `reddit_stocks.db` is created at runtime** in the same directory as the scripts. Do not hardcode an absolute path.
5. **Streamlit `app.py` only reads from the database.** It never calls `scraper.py`, `sentiment.py`, or `scheduler.py`.
6. **`main.py` only starts the scheduler.** All logic is in `scheduler.py`.
7. **All datetime strings stored in the database are UTC**, not local time.
8. **Sentiment is analyzed per (post × ticker) pair.** If a post mentions 3 tickers, Gemini is called 3 times.

---

## 17. Dependency Versions Known to Work Together

If pip raises conflicts, install in this order:
```
pip install python-dotenv requests
pip install google-generativeai
pip install apscheduler
pip install streamlit pandas plotly
```

---

*End of specification. Implement all files exactly as described.*
n. Implement all files exactly as described.*
End of specification. Implement all files exactly as described.*
