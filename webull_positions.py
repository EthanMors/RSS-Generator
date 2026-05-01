import os
import pickle
from dotenv import load_dotenv
from webull import webull

load_dotenv()

WEBULL_EMAIL = os.getenv("WEBULL_EMAIL", "")
WEBULL_PASSWORD = os.getenv("WEBULL_PASSWORD", "")
WEBULL_DEVICE_NAME = os.getenv("WEBULL_DEVICE_NAME", "RSS-Generator")
CREDENTIALS_FILE = "webull_credentials.json"


def connect() -> webull:
    """Authenticate and return a logged-in webull client (read-only session)."""
    wb = webull()

    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "rb") as f:
                creds = pickle.load(f)
            wb.api_login(
                access_token=creds.get("accessToken", ""),
                refresh_token=creds.get("refreshToken", ""),
                token_expire=creds.get("tokenExpireTime", ""),
                uuid=creds.get("uuid", ""),
            )
            if wb.is_logged_in():
                print("Logged in via saved credentials.", flush=True)
                return wb
            print("Token expired, attempting refresh...", flush=True)
            result = wb.refresh_login(save_token=True)
            if "accessToken" in result and wb.is_logged_in():
                print("Token refreshed successfully.", flush=True)
                return wb
        except Exception:
            pass
        print("Saved credentials invalid. Re-authenticating...", flush=True)

    email = WEBULL_EMAIL or input("Webull email: ").strip()
    password = WEBULL_PASSWORD or input("Webull password: ").strip()

    print("Sending MFA code to your registered email/phone...", flush=True)
    wb.get_mfa(email)
    mfa_code = input("Enter MFA code: ").strip()

    result = wb.login(
        username=email,
        password=password,
        device_name=WEBULL_DEVICE_NAME,
        mfa=mfa_code,
        save_token=True,
    )

    if "accessToken" not in result:
        raise RuntimeError(f"Webull login failed: {result.get('msg', result)}")

    print("Login successful. Credentials saved for future runs.", flush=True)
    return wb


def get_positions(wb: webull) -> list[dict]:
    """Return current holdings as a list of position dicts."""
    try:
        raw = wb.get_positions()
    except (KeyError, TypeError):
        return []

    if not raw:
        return []

    positions = []
    for item in raw:
        ticker = item.get("ticker", {})
        positions.append({
            "ticker": ticker.get("symbol", ""),
            "name": ticker.get("name", ""),
            "quantity": float(item.get("position", 0) or 0),
            "cost_basis": float(item.get("costPrice", 0) or 0),
            "current_price": float(item.get("lastPrice", 0) or 0),
            "market_value": float(item.get("marketValue", 0) or 0),
            "unrealized_pnl": float(item.get("unrealizedProfitLoss", 0) or 0),
            "unrealized_pnl_pct": float(item.get("unrealizedProfitLossRate", 0) or 0) * 100,
        })
    return positions


def get_account_summary(wb: webull) -> dict:
    """Return portfolio totals as a flat dict of {key: float}."""
    try:
        portfolio = wb.get_portfolio()
    except (KeyError, TypeError):
        return {}
    return {k: float(v) if v else 0.0 for k, v in portfolio.items()}


def display_positions() -> None:
    """Connect to Webull and print account summary and current positions."""
    wb = connect()

    print("\n=== Account Summary ===", flush=True)
    try:
        summary = get_account_summary(wb)
        if summary:
            for key, val in summary.items():
                print(f"  {key}: ${val:,.2f}", flush=True)
        else:
            print("  No account summary available.", flush=True)
    except Exception as e:
        print(f"  Could not fetch account summary: {e}", flush=True)

    print("\n=== Current Positions ===", flush=True)
    try:
        positions = get_positions(wb)
        if not positions:
            print("  No open positions.", flush=True)
            return
        for pos in positions:
            pnl_sign = "+" if pos["unrealized_pnl"] >= 0 else ""
            print(
                f"  {pos['ticker']:<6}  {pos['name']:<30}"
                f"  Qty: {pos['quantity']:.4g}"
                f"  Cost: ${pos['cost_basis']:.2f}"
                f"  Price: ${pos['current_price']:.2f}"
                f"  Mkt Value: ${pos['market_value']:,.2f}"
                f"  P&L: {pnl_sign}${pos['unrealized_pnl']:,.2f}"
                f" ({pnl_sign}{pos['unrealized_pnl_pct']:.2f}%)",
                flush=True,
            )
    except Exception as e:
        print(f"  Could not fetch positions: {e}", flush=True)
