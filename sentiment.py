import subprocess
import json
import re


def analyze_sentiment(title: str, body: str, ticker: str) -> dict:
    try:
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

        result = subprocess.run(
            ["gemini", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"gemini CLI exited {result.returncode}: {result.stderr.strip()}")

        response_text = result.stdout.strip()

        # Remove markdown code fences if present
        response_text = re.sub(r"```(?:json)?\s*", "", response_text).strip()
        parsed = json.loads(response_text)

        # Validate and clamp sentiment_score
        sentiment_score = max(-1.0, min(1.0, float(parsed["sentiment_score"])))

        # Validate sentiment_label
        sentiment_label = parsed["sentiment_label"]
        if sentiment_label not in ["positive", "negative", "neutral"]:
            if sentiment_score > 0.1:
                sentiment_label = "positive"
            elif sentiment_score < -0.1:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"

        return {
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
        }

    except Exception as e:
        print(f"[SENTIMENT] Error analyzing sentiment for {ticker}: {e}")
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}
