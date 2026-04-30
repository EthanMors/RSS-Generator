import config
import scraper
import sentiment

print("Fetching posts...", flush=True)
posts = scraper.fetch_posts(config.SUBREDDIT, limit=20)
print(f"Fetched {len(posts)} posts. Searching for Apple mentions...", flush=True)

TARGET_TICKER = "AAPL"
found = False

for post in posts:
    combined_text = post["title"] + " " + post.get("selftext", "")
    if "apple" in combined_text.lower() or "aapl" in combined_text.lower():
        found = True
        print(f"\nPost: {post['title']}", flush=True)
        print(f"Body: {post.get('selftext', '')[:300]}", flush=True)
        print(f"Analyzing sentiment for {TARGET_TICKER}...", flush=True)
        result = sentiment.analyze_sentiment(post["title"], post.get("selftext", ""), TARGET_TICKER)
        print(f"Sentiment: {result}", flush=True)
        break

if not found:
    print("No Apple posts found. Analyzing the first post anyway...", flush=True)
    post = posts[0]
    print(f"\nPost: {post['title']}", flush=True)
    print(f"Body: {post.get('selftext', '')[:300]}", flush=True)
    result = sentiment.analyze_sentiment(post["title"], post.get("selftext", ""), TARGET_TICKER)
    print(f"Sentiment: {result}", flush=True)
