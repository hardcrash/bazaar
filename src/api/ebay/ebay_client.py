import requests
import base64
import logging

logger = logging.getLogger("BazaarPipeline")

class EbayClient:
    def __init__(self, client_id, client_secret, sandbox=True):
        """
        Initializes the connection client for the eBay REST Browse API ecosystem.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.sandbox = sandbox
        self.session = requests.Session()
        self.access_token = None

        # Determine the base environments
        if self.sandbox:
            self.auth_url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
            self.search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        else:
            self.auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
            self.search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

        # Automatically fetch an access token upon instantiating the class
        self._authenticate()

    def _authenticate(self):
        """
        Performs the OAuth2 Application Client Credentials Grant flow
        to capture an application access token.
        """
        # Encode application keys into basic auth header layout
        credential_string = f"{self.client_id}:{self.client_secret}"
        encoded_creds = base64.b64encode(credential_string.encode("utf-8")).decode("utf-8")

        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }

        try:
            response = self.session.post(self.auth_url, headers=headers, data=payload, timeout=10)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                logger.info("[✅] eBay Client application token secured successfully.")
            else:
                logger.error(f"[❌] OAuth Authentication Failed: {response.status_code} - {response.text}")
                self.access_token = None
        except Exception as e:
            logger.error(f"[❌] Critical network failure during token acquisition: {e}")
            self.access_token = None

    def search_items(self, query, limit=50, offset=0, condition_id=None):
        """
        Queries the eBay Browse API for active product snapshots.
        Supports page offsets and native item condition backend filters.
        """
        if not self.access_token:
            logger.error("[-] Request blocked: No valid access token present on client.")
            return []

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Build base params dictionary
        params = {
            "q": query,
            "limit": limit
        }

        # Turning Pages: Only append offset if we are moving past page 1
        if offset > 0:
            params["offset"] = offset

        # Strict Categorization: Apply structural condition filtering to eBay's database indexes
        if condition_id:
            # Condition 3000 = Used/Working, Condition 7000 = For Parts/Broken
            params["filter"] = f"conditions:{{{condition_id}}}"

        try:
            response = self.session.get(self.search_url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Returns the items array inside the response body
                return data.get("itemSummaries", [])
            elif response.status_code == 404:
                return []
            else:
                logger.warning(f"[-] eBay API Search Error: Status {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"[-] Critical exception during eBay endpoint search execution: {e}")
            return []
