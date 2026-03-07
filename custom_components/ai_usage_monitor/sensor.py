"""Sensor platform for AI Usage Monitor."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_CLAUDE_COOKIE,
    CONF_CLAUDE_ORG_ID,
    CONF_CURSOR_COOKIE,
    CONF_SCAN_INTERVAL,
    CURSOR_REQUEST_HEADERS,
    CURSOR_USAGE_URL,
    CLAUDE_USAGE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _fetch_cursor_usage(cookie: str) -> dict[str, Any]:
    """Fetch Cursor usage data."""
    async with aiohttp.ClientSession() as session:
        headers = {**CURSOR_REQUEST_HEADERS, "Cookie": cookie}
        async with session.post(
            CURSOR_USAGE_URL,
            headers=headers,
            json={},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Cursor API returned status {resp.status}")
            return await resp.json(content_type=None)


async def _fetch_claude_usage(cookie: str, org_id: str) -> dict[str, Any]:
    """Fetch Claude usage data from the internal API.

    This uses the internal claude.ai API which requires a valid session cookie.
    The user needs to extract their sessionKey cookie from claude.ai.
    """
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        }

        # Try the bootstrap endpoint first to get usage info
        url = CLAUDE_USAGE_URL
        if org_id:
            url = f"https://claude.ai/api/organizations/{org_id}/usage"

        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Claude API returned status {resp.status}")
            return await resp.json()


class CursorUsageCoordinator(DataUpdateCoordinator):
    """Coordinator for Cursor usage data."""

    def __init__(self, hass: HomeAssistant, cookie: str, interval: int) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Cursor Usage",
            update_interval=timedelta(seconds=interval),
        )
        self._cookie = cookie

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Cursor API."""
        try:
            return await _fetch_cursor_usage(self._cookie)
        except Exception as err:
            raise UpdateFailed(f"Error fetching Cursor usage: {err}") from err


class ClaudeUsageCoordinator(DataUpdateCoordinator):
    """Coordinator for Claude usage data."""

    def __init__(
        self, hass: HomeAssistant, cookie: str, org_id: str, interval: int
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Claude Usage",
            update_interval=timedelta(seconds=interval),
        )
        self._cookie = cookie
        self._org_id = org_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Claude API."""
        try:
            return await _fetch_claude_usage(self._cookie, self._org_id)
        except Exception as err:
            raise UpdateFailed(f"Error fetching Claude usage: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    config = entry.data
    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    entities: list[SensorEntity] = []

    # --- Cursor sensors ---
    cursor_cookie = config.get(CONF_CURSOR_COOKIE, "")
    if cursor_cookie:
        cursor_coordinator = CursorUsageCoordinator(hass, cursor_cookie, interval)
        await cursor_coordinator.async_config_entry_first_refresh()

        entities.extend(
            [
                CursorAutoUsageSensor(cursor_coordinator, entry),
                CursorApiUsageSensor(cursor_coordinator, entry),
                CursorTotalUsageSensor(cursor_coordinator, entry),
                CursorSpendSensor(cursor_coordinator, entry),
            ]
        )

    # --- Claude sensors ---
    claude_cookie = config.get(CONF_CLAUDE_COOKIE, "")
    if claude_cookie:
        claude_org_id = config.get(CONF_CLAUDE_ORG_ID, "")
        claude_coordinator = ClaudeUsageCoordinator(
            hass, claude_cookie, claude_org_id, interval
        )
        try:
            await claude_coordinator.async_config_entry_first_refresh()
            entities.append(ClaudeUsageSensor(claude_coordinator, entry))
        except UpdateFailed:
            _LOGGER.warning(
                "Could not fetch Claude usage data. "
                "The internal API may have changed. Check your cookie and org ID."
            )

    async_add_entities(entities, True)


# =============================================================================
# Cursor Sensors
# =============================================================================


class CursorBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Cursor usage."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: CursorUsageCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        unit: str | None = "%",
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{entry.entry_id}_cursor_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_cursor")},
            "name": "Cursor",
            "manufacturer": "Anysphere",
            "model": "Cursor IDE",
            "entry_type": "service",
        }


class CursorAutoUsageSensor(CursorBaseSensor):
    """Sensor for Cursor auto (agent) usage percentage."""

    def __init__(self, coordinator: CursorUsageCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            coordinator, entry, "auto_percent", "Auto Usage", "mdi:robot-outline"
        )

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            val = self.coordinator.data.get("planUsage", {}).get("autoPercentUsed")
            if val is not None:
                return round(val, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data or {}
        usage = data.get("planUsage", {})
        return {
            "display_message": data.get("autoModelSelectedDisplayMessage", ""),
        }


class CursorApiUsageSensor(CursorBaseSensor):
    """Sensor for Cursor API usage percentage."""

    def __init__(self, coordinator: CursorUsageCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            coordinator, entry, "api_percent", "API Usage", "mdi:api"
        )

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            val = self.coordinator.data.get("planUsage", {}).get("apiPercentUsed")
            if val is not None:
                return round(val, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data or {}
        return {
            "display_message": data.get("namedModelSelectedDisplayMessage", ""),
        }


class CursorTotalUsageSensor(CursorBaseSensor):
    """Sensor for Cursor total usage percentage."""

    def __init__(self, coordinator: CursorUsageCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            coordinator, entry, "total_percent", "Total Usage", "mdi:chart-donut"
        )

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            val = self.coordinator.data.get("planUsage", {}).get("totalPercentUsed")
            if val is not None:
                return round(val, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes with billing cycle info."""
        data = self.coordinator.data or {}
        usage = data.get("planUsage", {})
        attrs: dict[str, Any] = {}

        cycle_start = data.get("billingCycleStart")
        cycle_end = data.get("billingCycleEnd")
        if cycle_start:
            attrs["billing_cycle_start"] = cycle_start
        if cycle_end:
            attrs["billing_cycle_end"] = cycle_end

        attrs["total_spend"] = usage.get("totalSpend")
        attrs["included_spend"] = usage.get("includedSpend")
        attrs["limit"] = usage.get("limit")

        return attrs


class CursorSpendSensor(CursorBaseSensor):
    """Sensor for Cursor total spend in cents."""

    def __init__(self, coordinator: CursorUsageCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            entry,
            "total_spend",
            "Total Spend",
            "mdi:currency-usd",
            "USD",
        )
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the spend in dollars."""
        if self.coordinator.data:
            cents = self.coordinator.data.get("planUsage", {}).get("totalSpend")
            if cents is not None:
                return round(cents / 100, 2)
        return None


# =============================================================================
# Claude Sensors
# =============================================================================


class ClaudeUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Claude usage.

    The exact shape of the response depends on the internal API version.
    This sensor attempts to extract a usage percentage from the response.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:head-snowflake-outline"

    def __init__(
        self, coordinator: ClaudeUsageCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Claude Usage"
        self._attr_unique_id = f"{entry.entry_id}_claude_usage"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_claude")},
            "name": "Claude Code",
            "manufacturer": "Anthropic",
            "model": "Claude Pro/Max",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> float | None:
        """Try to extract usage percentage from the response."""
        data = self.coordinator.data
        if not data:
            return None

        # The internal API response format may vary.
        # Common patterns to look for:
        for key in ("percentUsed", "usage_percent", "percent_used", "usagePercent"):
            if key in data:
                return round(float(data[key]), 2)

        # If the response has a nested structure
        if isinstance(data, dict):
            for _, v in data.items():
                if isinstance(v, dict):
                    for key in (
                        "percentUsed",
                        "usage_percent",
                        "percent_used",
                        "usagePercent",
                    ):
                        if key in v:
                            return round(float(v[key]), 2)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw API response as attributes for debugging."""
        data = self.coordinator.data
        if not data:
            return {}
        # Flatten top-level keys as attributes (limit to safe types)
        attrs: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)):
                attrs[k] = v
        return attrs
