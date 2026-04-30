import re

# Mapping of company names and common nicknames to tickers
COMPANY_TO_TICKER = {
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "AMAZON": "AMZN",
    "META": "META",
    "FACEBOOK": "META",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
    "BERKSHIRE": "BRK",
    "JPMORGAN": "JPM",
    "CHASE": "JPM",
    "VISA": "V",
    "DISNEY": "DIS",
    "NETFLIX": "NFLX",
    "GAMESTOP": "GME",
    "WALMART": "WMT",
    "COSTCO": "COST",
    "STARBUCKS": "SBUX",
    "MCDONALDS": "MCD",
    "FORD": "F",
    "PALANTIR": "PLTR",
    "ROBINHOOD": "HOOD",
    "COINBASE": "COIN",
}

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

    text_upper = text.upper()
    found_tickers = {}

    # 1. Identify all candidates
    # Pattern for $TICKER
    dollar_matches = re.finditer(r"\$([A-Z]{1,5})\b", text_upper)
    for match in dollar_matches:
        ticker = match.group(1)
        # Store original start/end to avoid double counting same text segment
        # but for simplicity, we'll just track if we've "used" this span
        # Actually, let's just collect all matches and map them to canonical tickers.
        
    # Pattern for standalone words
    word_matches = re.finditer(r"\b([A-Z]{1,15})\b", text_upper)
    
    # We'll use a set of spans to ensure we don't count the same characters twice
    # e.g., "$AAPL" matches both patterns.
    used_spans = set()

    def add_to_found(ticker_cand, span):
        if span in used_spans:
            return
        
        canonical = None
        # Check if it's a known company name
        if ticker_cand in COMPANY_TO_TICKER:
            canonical = COMPANY_TO_TICKER[ticker_cand]
        # Check if it's a known ticker
        elif ticker_cand in KNOWN_TICKERS:
            canonical = ticker_cand
        
        if canonical and canonical not in FALSE_POSITIVES:
            found_tickers[canonical] = found_tickers.get(canonical, 0) + 1
            used_spans.add(span)

    # First pass: Dollar signs (stronger signal)
    dollar_matches = list(re.finditer(r"\$([A-Z]{1,5})\b", text_upper))
    for match in dollar_matches:
        ticker_cand = match.group(1)
        # The span includes the '$', but we want to mark the word as used too
        add_to_found(ticker_cand, match.span())
        # Also mark the word portion as used to prevent standalone word match
        # The word starts at match.start() + 1
        used_spans.add((match.start() + 1, match.end()))

    # Second pass: Standalone words (Company Names and Known Tickers)
    word_matches = list(re.finditer(r"\b([A-Z]{1,15})\b", text_upper))
    for match in word_matches:
        ticker_cand = match.group(1)
        add_to_found(ticker_cand, match.span())

    return found_tickers
