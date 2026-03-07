# AI Usage Monitor for Home Assistant

A [HACS](https://hacs.xyz) custom integration that tracks your **Cursor** and **Claude Code** plan usage directly in Home Assistant, with a custom Lovelace card that auto-refreshes every time you open/focus the dashboard.

## Features

- **Cursor sensors** — Auto (Agent) %, API (Named model) %, Total %, and spend in USD
- **Claude sensor** — Plan usage percentage *(experimental — see note below)*
- **Custom Lovelace card** — Color-coded progress bars, auto-refreshes on page focus/visibility
- Standard HA `update_entity` support for automations

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → three-dot menu → **Custom repositories**
2. Add this repo URL, category **Integration**
3. Install **AI Usage Monitor**
4. Copy `www/ai-usage-monitor-card.js` to your HA `www/` folder (or it should be copied automatically)
5. Restart Home Assistant

### Manual

1. Copy `custom_components/ai_usage_monitor/` into your HA `config/custom_components/` directory
2. Copy `www/ai-usage-monitor-card.js` into `config/www/`
3. Restart Home Assistant

## Configuration

Go to **Settings → Devices & Services → Add Integration → AI Usage Monitor**.

### Getting your Cursor cookie

1. Open [cursor.com/dashboard](https://cursor.com/dashboard) in your browser
2. Open DevTools → **Network** tab
3. Look for the `get-current-period-usage` request
4. Copy the full `Cookie` header value

The cookie must include `WorkosCursorSessionToken`. Example:

```
workos_id=user_XXXXX; WorkosCursorSessionToken=user_XXXXX%3A%3AeyJhb...
```

### Getting your Claude cookie *(experimental)*

> **Note:** Anthropic does not provide a public API for subscription usage percentage. There is an [open feature request](https://github.com/anthropics/claude-code/issues/19880) for this. The Claude sensor relies on internal/undocumented APIs that may change at any time.

1. Open [claude.ai/settings/usage](https://claude.ai/settings/usage) in your browser
2. Open DevTools → **Network** tab
3. Look for API requests related to usage (e.g., requests to `/api/usage` or `/api/organizations/...`)
4. Copy the full `Cookie` header value
5. Note your organization UUID from the URL (if applicable)

### Config fields

| Field | Required | Description |
|---|---|---|
| Cursor Session Cookie | No* | Full cookie string from cursor.com |
| Claude Session Cookie | No* | Full cookie string from claude.ai |
| Claude Organization ID | No | Your org UUID from claude.ai URL |
| Update interval | No | Polling interval in seconds (default: 300) |

\* At least one service must be configured.

## Sensors created

### Cursor

| Entity | Description |
|---|---|
| `sensor.cursor_auto_usage` | Agent/Auto model usage % |
| `sensor.cursor_api_usage` | API/Named model usage % |
| `sensor.cursor_total_usage` | Combined total usage % |
| `sensor.cursor_total_spend` | Total spend in USD this billing cycle |

### Claude

| Entity | Description |
|---|---|
| `sensor.claude_usage` | Plan usage % (experimental) |

## Lovelace Card

### Add the resource

Go to **Settings → Dashboards → Resources** (or edit your dashboard YAML), add:

```yaml
url: /local/ai-usage-monitor-card.js
type: module
```

### Card configuration

```yaml
type: custom:ai-usage-monitor-card
title: AI Usage
cursor_auto_entity: sensor.cursor_auto_usage
cursor_api_entity: sensor.cursor_api_usage
cursor_total_entity: sensor.cursor_total_usage
cursor_spend_entity: sensor.cursor_total_spend
claude_entity: sensor.claude_usage
```

The card automatically calls `homeassistant.update_entity` for all configured entities whenever the browser tab gains focus or visibility, so your data is always fresh when you look at the dashboard.

### Card options

| Option | Default | Description |
|---|---|---|
| `title` | `AI Usage` | Card title |
| `cursor_auto_entity` | | Entity ID for Cursor auto usage |
| `cursor_api_entity` | | Entity ID for Cursor API usage |
| `cursor_total_entity` | | Entity ID for Cursor total usage |
| `cursor_spend_entity` | | Entity ID for Cursor spend |
| `claude_entity` | | Entity ID for Claude usage |
| `show_cursor` | `true` | Show Cursor section |
| `show_claude` | `true` | Show Claude section |

## Cookie expiration

Session cookies expire periodically. When your sensors show `unavailable`, you'll need to re-extract the cookie from your browser and update the integration config via **Settings → Devices & Services → AI Usage Monitor → Configure**.

A future version may support long-lived tokens if/when the services provide them.

## License

MIT
