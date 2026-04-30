import re

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

FALSE_POSITIVES = {"A", "I", "AT", "BE", "BY", "DO", "GO", "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OK", "ON", "OR", "SO", "TO", "UP", "US", "WE"}


def extract_tickers(text: str) -> dict[str, int]:
    if not text:
        return {}

    text = text.upper()
    tickers = {}

    # Method 1: Dollar-sign prefix
    dollar_matches = re.findall(r"\$([A-Z]{1,5})\b", text)
    for ticker in dollar_matches:
        tickers[ticker] = tickers.get(ticker, 0) + 1

    # Method 2: Known tickers list
    word_matches = re.findall(r"\b([A-Z]{1,5})\b", text)
    for ticker in word_matches:
        if ticker in KNOWN_TICKERS:
            tickers[ticker] = tickers.get(ticker, 0) + 1

    # Remove false positives
    for fp in FALSE_POSITIVES:
        tickers.pop(fp, None)

    return tickers
