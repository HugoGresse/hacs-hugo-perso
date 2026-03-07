"""Constants for AI Usage Monitor."""

DOMAIN = "ai_usage_monitor"

CONF_CURSOR_COOKIE = "cursor_cookie"
CONF_CLAUDE_COOKIE = "claude_cookie"
CONF_CLAUDE_ORG_ID = "claude_org_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

    CURSOR_USAGE_URL = "https://cursor.com/api/dashboard/get-current-period-usage"
    CLAUDE_USAGE_URL = "https://claude.ai/api/usage"

    CURSOR_REQUEST_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:115.0) Gecko/20100101 Firefox/115.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://cursor.com",
        "Referer": "https://cursor.com/dashboard",
        "DNT": "1",
        "Sec-GPC": "1",
    "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
