import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import database
import config

st.set_page_config(
    page_title="Reddit Stock Sentiment",
    page_icon="📈",
    layout="wide"
)

database.initialize_db()

st.title("📈 Reddit Stock Sentiment Dashboard")
st.subheader(f"Tracking r/{config.SUBREDDIT}")

# Date Selector Sidebar
st.sidebar.header("Filters")

today = datetime.utcnow().date()
selected_date = st.sidebar.date_input(
    "Select Date",
    value=today,
    min_value=today - timedelta(days=30),
    max_value=today,
)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# Load Data
daily_data = database.get_daily_summary(selected_date_str, config.SUBREDDIT)
recent_mentions = database.get_recent_ticker_mentions(config.SUBREDDIT, limit=500)

df_daily = pd.DataFrame(daily_data) if daily_data else pd.DataFrame()
df_mentions = pd.DataFrame(recent_mentions) if recent_mentions else pd.DataFrame()

# Metrics Row — 3 columns
col1, col2, col3 = st.columns(3)

# col1 — Total Unique Tickers Today
with col1:
    count = len(df_daily) if not df_daily.empty else 0
    st.metric("Unique Tickers Today", count)

# col2 — Most Mentioned Ticker
with col2:
    if not df_daily.empty:
        top = df_daily.iloc[0]
        st.metric("Most Mentioned", top["ticker"], f"{int(top['total_mentions'])} mentions")
    else:
        st.metric("Most Mentioned", "—")

# col3 — Average Sentiment Today
with col3:
    if not df_daily.empty:
        avg = df_daily["avg_sentiment"].mean()
        label = "Positive" if avg > 0.1 else ("Negative" if avg < -0.1 else "Neutral")
        st.metric("Avg Sentiment Today", f"{avg:.3f}", label)
    else:
        st.metric("Avg Sentiment Today", "—")

# Bar Chart — Top 10 Tickers by Mentions
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

# Sentiment Over Time — Line Chart
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

# Raw Data Table
st.subheader("Recent Ticker Mentions (last 500)")

if not df_mentions.empty:
    display_cols = ["ticker", "mention_count", "sentiment_score", "sentiment_label", "date", "post_id"]
    available = [c for c in display_cols if c in df_mentions.columns]
    st.dataframe(df_mentions[available], use_container_width=True, height=400)
else:
    st.info("No mention data yet.")

# Refresh Button
st.divider()
if st.button("🔄 Refresh Dashboard"):
    st.rerun()

st.caption(f"Data from r/{config.SUBREDDIT} | Scraper runs every {config.POLL_INTERVAL_MINUTES} minutes | DB: {config.DB_PATH}")
