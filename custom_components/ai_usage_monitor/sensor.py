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
    CLAUDE_REQUEST_HEADERS,
    CLAUDE_USAGE_URL,
    CONF_CLAUDE_TOKEN,
    CONF_CURSOR_COOKIE,
    CONF_SCAN_INTERVAL,
    CURSOR_REQUEST_HEADERS,
    CURSOR_USAGE_URL,
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


async def _fetch_claude_usage(token: str) -> dict[str, Any]:
    """Fetch Claude usage data from the Anthropic OAuth API.

    This uses the Anthropic OAuth usage endpoint which requires a valid
    Bearer token obtained via OAuth.
    """
    async with aiohttp.ClientSession() as session:
        headers = {
            **CLAUDE_REQUEST_HEADERS,
            "Authorization": f"Bearer {token}",
        }
        async with session.get(
            CLAUDE_USAGE_URL,
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
        self, hass: HomeAssistant, token: str, interval: int
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Claude Usage",
            update_interval=timedelta(seconds=interval),
        )
        self._token = token

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Claude API."""
        try:
            return await _fetch_claude_usage(self._token)
        except Exception as err:
            raise UpdateFailed(f"Error fetching Claude usage: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    config = {**entry.data, **entry.options}
    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    entities: list[SensorEntity] = []

    # --- Cursor sensors ---
    cursor_cookie = config.get(CONF_CURSOR_COOKIE, "")
    if cursor_cookie:
        cursor_coordinator = CursorUsageCoordinator(hass, cursor_cookie, interval)
        await cursor_coordinator.async_refresh()
        if cursor_coordinator.last_exception:
            _LOGGER.warning(
                "Could not fetch initial Cursor usage data: %s. "
                "Sensors will be unavailable until the next scheduled update.",
                cursor_coordinator.last_exception,
            )

        entities.extend(
            [
                CursorAutoUsageSensor(cursor_coordinator, entry),
                CursorApiUsageSensor(cursor_coordinator, entry),
                CursorTotalUsageSensor(cursor_coordinator, entry),
                CursorSpendSensor(cursor_coordinator, entry),
            ]
        )

    # --- Claude sensors ---
    claude_token = config.get(CONF_CLAUDE_TOKEN, "")
    if claude_token:
        claude_coordinator = ClaudeUsageCoordinator(hass, claude_token, interval)
        await claude_coordinator.async_refresh()
        if claude_coordinator.last_exception:
            _LOGGER.warning(
                "Could not fetch initial Claude usage data: %s. "
                "Check your Bearer token. "
                "Sensors will be unavailable until the next scheduled update.",
                claude_coordinator.last_exception,
            )
        entities.extend(
            [
                ClaudeFiveHourUsageSensor(claude_coordinator, entry),
                ClaudeSevenDayUsageSensor(claude_coordinator, entry),
            ]
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
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AI Providers",
            "entry_type": "service",
        }


class CursorAutoUsageSensor(CursorBaseSensor):
    """Sensor for Cursor auto (agent) usage percentage."""

    def __init__(self, coordinator: CursorUsageCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            coordinator, entry, "auto_percent", "Cursor Auto Usage", "mdi:robot-outline"
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
        return {
            "display_message": data.get("autoModelSelectedDisplayMessage", ""),
        }


class CursorApiUsageSensor(CursorBaseSensor):
    """Sensor for Cursor API usage percentage."""

    def __init__(self, coordinator: CursorUsageCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            coordinator, entry, "api_percent", "Cursor API Usage", "mdi:api"
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
            coordinator, entry, "total_percent", "Cursor Total Usage", "mdi:chart-donut"
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
            "Cursor Total Spend",
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


class ClaudeBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Claude usage."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:head-snowflake-outline"

    def __init__(
        self,
        coordinator: ClaudeUsageCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_claude_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AI Providers",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> float | None:
        """Return the utilization percentage for this window."""
        data = self.coordinator.data
        if not data:
            return None
        window = data.get(self._key, {})
        utilization = window.get("utilization")
        if utilization is not None:
            return round(float(utilization), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return resets_at as an attribute."""
        data = self.coordinator.data
        if not data:
            return {}
        window = data.get(self._key, {})
        attrs: dict[str, Any] = {}
        resets_at = window.get("resets_at")
        if resets_at is not None:
            attrs["resets_at"] = resets_at
        return attrs


class ClaudeFiveHourUsageSensor(ClaudeBaseSensor):
    """Sensor for Claude 5-hour usage utilization."""

    def __init__(
        self, coordinator: ClaudeUsageCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "five_hour", "Claude Five Hour Usage")


class ClaudeSevenDayUsageSensor(ClaudeBaseSensor):
    """Sensor for Claude 7-day usage utilization."""

    def __init__(
        self, coordinator: ClaudeUsageCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "seven_day", "Claude Seven Day Usage")
