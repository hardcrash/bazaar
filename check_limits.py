# check_limits.py
import requests
import json
from src.util.config_loader import load_yaml

def get_oauth_token(client_id, client_secret, is_sandbox):
    """Fetches a temporary application access token to query developer metrics."""
    domain = "api.sandbox.ebay.com" if is_sandbox else "api.ebay.com"
    url = f"https://{domain}/identity/v1/oauth2/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"  # Scopes required for analytics querying
    }

    response = requests.post(url, headers=headers, data=data, auth=(client_id, client_secret))
    if response.status_code != 200:
        raise Exception(f"OAuth token generation failed: {response.text}")
    return response.json().get("access_token")

def fetch_and_print_rate_limits():
    print("🕵️‍♂️ Initializing eBay Quota & Rate Limit Inspection...")

    # Load settings exactly how your main script pulls them
    try:
        config = load_yaml("config.yaml")
        creds = load_yaml("config_credentials.yaml")
        use_sandbox = config.get("use_sandbox", True)
        env_key = "sandbox" if use_sandbox else "production"

        client_id = creds[env_key]["client_id"]
        client_secret = creds[env_key]["client_secret"]
    except Exception as e:
        print(f"❌ Configuration error loading your secret keysets: {e}")
        return

    # Authenticate
    try:
        token = get_oauth_token(client_id, client_secret, use_sandbox)
    except Exception as e:
        print(f"❌ Failed to authorize against eBay Authentication servers: {e}")
        return

    # Hit the Developer Analytics endpoint
    domain = "api.sandbox.ebay.com" if use_sandbox else "api.ebay.com"
    analytics_url = f"https://{domain}/developer/analytics/v1_beta/rate_limit"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    # Query parameters targeting your specific platform vectors
    params = {
        "api_context": "buy",
        "api_name": "browse"
    }

    print(f"📡 Querying metadata limits from environment: [{env_key.upper()}]...")
    response = requests.get(analytics_url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"❌ eBay Analytics endpoint rejected request (Status {response.status_code}):")
        print(response.text)
        return

    data = response.json()
    rate_limits = data.get("rateLimits", [])

    if not rate_limits:
        print("⚠️ No matching rate limits returned for context: 'buy/browse'.")
        print("Your keys are fully clear or have not initialized baseline API tracking logs yet.")
        return

    print("\n=======================================================")
    print("📈 EBAY APPLICATION RUNTIME ALLOCATION ANALYSIS")
    print("=======================================================")

    for limit_block in rate_limits:
        context = limit_block.get("apiContext")
        api = limit_block.get("apiName")
        version = limit_block.get("apiVersion")

        print(f"\n📂 API Target: {context.upper()} -> {api.upper()} ({version})")
        print("-" * 55)

        for resource in limit_block.get("resources", []):
            resource_name = resource.get("name")
            for rate in resource.get("rates", []):
                total_limit = rate.get("limit")
                calls_made = rate.get("count")
                remaining = rate.get("remaining")
                reset_time = rate.get("reset")
                window_seconds = rate.get("timeWindow")

                # Turn time windows into readable durations
                window_desc = f"{int(window_seconds / 3600)}h" if window_seconds >= 3600 else f"{int(window_seconds / 60)}m"

                print(f"📍 Method Context:  {resource_name}")
                print(f"   ▪ Allocation Window:  {window_desc}")
                print(f"   ▪ Used Today:         {calls_made} calls")
                print(f"   ▪ Remaining Space:    {remaining} / {total_limit} calls left")
                print(f"   ▪ Window Reset Time:  {reset_time}")
                print()

if __name__ == "__main__":
    fetch_and_print_rate_limits()
