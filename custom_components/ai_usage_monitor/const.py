"""Constants for AI Usage Monitor."""

DOMAIN = "ai_usage_monitor"

CONF_CURSOR_COOKIE = "cursor_cookie"
CONF_CLAUDE_COOKIE = "claude_cookie"
CONF_CLAUDE_ORG_ID = "claude_org_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

CURSOR_USAGE_URL = "https://cursor.com/api/dashboard/get-current-period-usage"
CLAUDE_USAGE_URL = "https://claude.ai/api/usage"
