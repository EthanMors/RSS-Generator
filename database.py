import sqlite3
import config
from datetime import datetime, timezone


def initialize_db():
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
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
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
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
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {config.DB_PATH}")


def post_exists(post_id: str) -> bool:
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posts WHERE post_id = ?", (post_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result


def insert_post(post: dict) -> None:
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO posts (post_id, subreddit, title, selftext, author, score,
            num_comments, created_utc, url, permalink, fetched_at, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post["post_id"],
        post["subreddit"],
        post["title"],
        post["selftext"],
        post["author"],
        post["score"],
        post["num_comments"],
        post["created_utc"],
        post["url"],
        post["permalink"],
        post["fetched_at"],
        post["date"],
    ))
    conn.commit()
    conn.close()


def insert_ticker_mention(mention: dict) -> None:
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ticker_mentions (ticker, post_id, mention_count, sentiment_score,
            sentiment_label, timestamp, date, subreddit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mention["ticker"],
        mention["post_id"],
        mention["mention_count"],
        mention["sentiment_score"],
        mention["sentiment_label"],
        mention["timestamp"],
        mention["date"],
        mention["subreddit"],
    ))
    conn.commit()
    conn.close()


def upsert_daily_summary(date: str, ticker: str, subreddit: str) -> None:
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as post_count,
               SUM(mention_count) as total_mentions,
               AVG(sentiment_score) as avg_sentiment,
               MIN(sentiment_score) as min_sentiment,
               MAX(sentiment_score) as max_sentiment
        FROM ticker_mentions
        WHERE date = ? AND ticker = ? AND subreddit = ?
    """, (date, ticker, subreddit))

    row = cursor.fetchone()
    post_count = row[0] or 0
    total_mentions = row[1] or 0
    avg_sentiment = row[2] or 0.0
    min_sentiment = row[3] or 0.0
    max_sentiment = row[4] or 0.0

    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    cursor.execute("""
        INSERT OR REPLACE INTO daily_summary
            (date, ticker, total_mentions, avg_sentiment, min_sentiment, max_sentiment,
             post_count, subreddit, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (date, ticker, total_mentions, avg_sentiment, min_sentiment, max_sentiment,
          post_count, subreddit, last_updated))

    conn.commit()
    conn.close()


def get_daily_summary(date: str, subreddit: str) -> list[dict]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM daily_summary
        WHERE date = ? AND subreddit = ?
        ORDER BY total_mentions DESC
    """, (date, subreddit))

    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result


def get_recent_ticker_mentions(subreddit: str, limit: int = 200) -> list[dict]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM ticker_mentions
        WHERE subreddit = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (subreddit, limit))

    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result


def get_sentiment_over_time(ticker: str, subreddit: str, days: int = 7) -> list[dict]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date, avg_sentiment, total_mentions
        FROM daily_summary
        WHERE ticker = ? AND subreddit = ?
        ORDER BY date ASC
        LIMIT ?
    """, (ticker, subreddit, days))

    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result
