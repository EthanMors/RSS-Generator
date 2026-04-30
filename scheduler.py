from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import config
import database
import scraper
import parser
import sentiment


def run_pipeline() -> None:
    try:
        # Step 1: Print start message
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[PIPELINE] Starting poll at {current_time}")

        # Step 2: Fetch posts
        posts = scraper.fetch_posts(config.SUBREDDIT, limit=config.REDDIT_POST_LIMIT)
        print(f"[PIPELINE] Fetched {len(posts)} posts from r/{config.SUBREDDIT}")

        # Step 3: For each post in posts
        for post in posts:

            # 3a. Skip if already processed
            if database.post_exists(post["post_id"]):
                continue

            # 3b. Insert post into database
            database.insert_post(post)

            # 3c. Combine title and body text
            combined_text = post["title"] + " " + post.get("selftext", "")

            # 3d. Extract tickers
            tickers = parser.extract_tickers(combined_text)
            if not tickers:
                continue

            # 3e. For each (ticker, count) in tickers.items()
            for ticker, count in tickers.items():

                # 3e-i. Run sentiment analysis
                sentiment_result = sentiment.analyze_sentiment(
                    title=post["title"],
                    body=post.get("selftext", ""),
                    ticker=ticker
                )

                # 3e-ii. Build mention dict and insert
                mention = {
                    "ticker": ticker,
                    "post_id": post["post_id"],
                    "mention_count": count,
                    "sentiment_score": sentiment_result["sentiment_score"],
                    "sentiment_label": sentiment_result["sentiment_label"],
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "date": post["date"],
                    "subreddit": config.SUBREDDIT,
                }
                database.insert_ticker_mention(mention)

                # 3e-iii. Update daily summary
                database.upsert_daily_summary(
                    date=post["date"],
                    ticker=ticker,
                    subreddit=config.SUBREDDIT
                )

        # Step 4: Print completion message
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[PIPELINE] Poll complete at {current_time}")

    except Exception as e:
        print(f"[PIPELINE] ERROR in pipeline: {e}")


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
