import requests
from datetime import datetime, timezone
import config


def fetch_posts(subreddit: str, limit: int = 100) -> list[dict]:
    try:
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
        headers = {
            "User-Agent": config.USER_AGENT
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        posts = []
        for child in data["data"]["children"]:
            post_data = child["data"]

            # Skip if required fields are missing
            if not post_data.get("id") or not post_data.get("title") or post_data.get("created_utc") is None:
                continue

            post = {
                "post_id": post_data["id"],
                "subreddit": post_data.get("subreddit", subreddit),
                "title": post_data["title"],
                "selftext": post_data.get("selftext", ""),
                "author": post_data.get("author", "[deleted]"),
                "score": post_data.get("score", 0),
                "num_comments": post_data.get("num_comments", 0),
                "created_utc": post_data["created_utc"],
                "url": post_data.get("url", ""),
                "permalink": post_data.get("permalink", ""),
            }

            post["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            post["date"] = datetime.utcfromtimestamp(post_data["created_utc"]).strftime("%Y-%m-%d")

            posts.append(post)

        return posts

    except Exception as e:
        print(f"[SCRAPER] Error fetching posts: {e}")
        return []
