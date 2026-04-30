import os
from dotenv import load_dotenv

load_dotenv()

REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
SUBREDDIT = os.getenv("SUBREDDIT")

# Validate — raise immediately on startup if any var is missing
for var_name, var_value in [
    ("REDDIT_USERNAME", REDDIT_USERNAME),
    ("SUBREDDIT", SUBREDDIT),
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
