import requests
import feedparser

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

print("--- Testing JSON API ---")
try:
    resp = requests.get(
        "https://www.reddit.com/r/artificial/hot.json?limit=5",
        headers={"User-Agent": UA},
        timeout=10
    )
    print(f"Status Code: {resp.status_code}")
except Exception as e:
    print(f"JSON Error: {e}")

print("\n--- Testing RSS API ---")
try:
    feed = feedparser.parse(
        "https://www.reddit.com/r/artificial/hot.rss",
        agent=UA
    )
    print(f"Feed entries: {len(feed.entries)}")
    if feed.entries:
        print(f"First title: {feed.entries[0].title}")
    else:
        print("RSS fetched but empty entries (maybe blocked?)")
except Exception as e:
    print(f"RSS Error: {e}")
