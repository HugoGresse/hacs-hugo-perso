"""Config flow for AI Usage Monitor."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CLAUDE_COOKIE,
    CONF_CLAUDE_ORG_ID,
    CONF_CURSOR_COOKIE,
    CONF_SCAN_INTERVAL,
    CURSOR_REQUEST_HEADERS,
    CURSOR_USAGE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _test_cursor_cookie(cookie: str) -> tuple[bool, str | None]:
    """Test if the Cursor cookie is valid. Returns (success, error_key)."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {**CURSOR_REQUEST_HEADERS, "Cookie": cookie}
            async with session.post(
                CURSOR_USAGE_URL, headers=headers, json={}, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                _LOGGER.debug("Cursor API response status: %s", resp.status)
                if resp.status == 200:
                    body = await resp.text()
                    try:
                        data = await resp.json(content_type=None)
                    except json.JSONDecodeError as json_err:
                        _LOGGER.debug(
                            "Cursor API returned non-JSON body (json_err=%s): %s",
                            json_err,
                            body[:200],
                        )
                        return False, "invalid_cursor_cookie"
                    _LOGGER.debug("Cursor API response keys: %s", list(data.keys()))
                    if "planUsage" in data:
                        return True, None
                    _LOGGER.debug("Cursor API response missing 'planUsage' key")
                    return False, "invalid_cursor_cookie"
                if resp.status in (401, 403):
                    _LOGGER.debug(
                        "Cursor API returned HTTP %s (invalid or expired cookie)", resp.status
                    )
                    return False, "cursor_auth_error"
                if resp.status == 429:
                    _LOGGER.debug("Cursor API returned HTTP 429 (rate limited)")
                    return False, "cursor_rate_limited"
                if resp.status >= 500:
                    _LOGGER.debug(
                        "Cursor API returned HTTP %s (server error)", resp.status
                    )
                    return False, "cursor_server_error"
                _LOGGER.debug(
                    "Cursor API returned unexpected HTTP %s", resp.status
                )
                return False, "cursor_unknown_error"
    except aiohttp.ClientError as err:
        _LOGGER.debug("Cursor API connection error: %s", err)
        return False, "cursor_connection_error"
    except Exception as err:
        _LOGGER.debug("Unexpected error testing Cursor cookie: %s", err)
        return False, "cursor_connection_error"


class AIUsageMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AI Usage Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cursor_cookie = user_input.get(CONF_CURSOR_COOKIE, "").strip()
            claude_cookie = user_input.get(CONF_CLAUDE_COOKIE, "").strip()
            claude_org_id = user_input.get(CONF_CLAUDE_ORG_ID, "").strip()

            if not cursor_cookie and not claude_cookie:
                errors["base"] = "no_services"
            else:
                # Test Cursor cookie if provided
                if cursor_cookie:
                    valid, error_key = await _test_cursor_cookie(cursor_cookie)
                    if not valid:
                        errors[CONF_CURSOR_COOKIE] = error_key

                if not errors:
                    await self.async_set_unique_id("ai_usage_monitor")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title="AI Usage Monitor",
                        data={
                            CONF_CURSOR_COOKIE: cursor_cookie,
                            CONF_CLAUDE_COOKIE: claude_cookie,
                            CONF_CLAUDE_ORG_ID: claude_org_id,
                            CONF_SCAN_INTERVAL: user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                        },
                    )

        existing = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CURSOR_COOKIE,
                        default=existing.get(CONF_CURSOR_COOKIE, ""),
                    ): str,
                    vol.Optional(
                        CONF_CLAUDE_COOKIE,
                        default=existing.get(CONF_CLAUDE_COOKIE, ""),
                    ): str,
                    vol.Optional(
                        CONF_CLAUDE_ORG_ID,
                        default=existing.get(CONF_CLAUDE_ORG_ID, ""),
                    ): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=existing.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> AIUsageMonitorOptionsFlow:
        """Get the options flow."""
        flow = AIUsageMonitorOptionsFlow()
        # Backwards compatibility for Home Assistant versions that do not
        # automatically set OptionsFlow.config_entry on instantiation.
        try:
            flow.config_entry = config_entry
        except AttributeError:
            # On newer HA versions, config_entry may be managed by the framework
            # and could be a read-only attribute.
            pass
        return flow


class AIUsageMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cursor_cookie = user_input.get(CONF_CURSOR_COOKIE, "").strip()
            claude_cookie = user_input.get(CONF_CLAUDE_COOKIE, "").strip()
            claude_org_id = user_input.get(CONF_CLAUDE_ORG_ID, "").strip()

            if not cursor_cookie and not claude_cookie:
                errors["base"] = "no_services"
            else:
                if cursor_cookie:
                    valid, error_key = await _test_cursor_cookie(cursor_cookie)
                    if not valid:
                        errors[CONF_CURSOR_COOKIE] = error_key

                if not errors:
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_CURSOR_COOKIE: cursor_cookie,
                            CONF_CLAUDE_COOKIE: claude_cookie,
                            CONF_CLAUDE_ORG_ID: claude_org_id,
                            CONF_SCAN_INTERVAL: user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                        },
                    )

        current = {**self.config_entry.data, **self.config_entry.options}
        form_defaults = user_input or current

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CURSOR_COOKIE,
                        default=form_defaults.get(CONF_CURSOR_COOKIE, ""),
                    ): str,
                    vol.Optional(
                        CONF_CLAUDE_COOKIE,
                        default=form_defaults.get(CONF_CLAUDE_COOKIE, ""),
                    ): str,
                    vol.Optional(
                        CONF_CLAUDE_ORG_ID,
                        default=form_defaults.get(CONF_CLAUDE_ORG_ID, ""),
                    ): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=form_defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                }
            ),
            errors=errors,
        )
