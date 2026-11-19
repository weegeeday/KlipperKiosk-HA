"""Sensor platform for KlipperKiosk."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import KlipperKioskConfigEntry, KlipperKioskCoordinator
from .entity import KlipperKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KlipperKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KlipperKiosk sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            KlipperKioskActiveTabUrlSensor(coordinator),
            KlipperKioskTabCountSensor(coordinator),
            KlipperKioskDeviceIpSensor(coordinator),
        ]
    )


class KlipperKioskActiveTabUrlSensor(KlipperKioskEntity, SensorEntity):
    """Sensor reporting the URL of the currently active tab."""

    _attr_translation_key = "active_tab_url"
    _attr_icon = "mdi:web"

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "active_tab_url")

    @property
    def native_value(self) -> str | None:
        """Return the active tab's configured URL."""
        active_tab = self.coordinator.data.status.active_tab
        return active_tab.url if active_tab else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return resolved URL and tab metadata."""
        active_tab = self.coordinator.data.status.active_tab
        if not active_tab:
            return {}
        attrs: dict[str, Any] = {
            "tab_id": active_tab.id,
            "tab_title": active_tab.title,
        }
        if active_tab.resolved_url:
            attrs["resolved_url"] = active_tab.resolved_url
        return attrs


class KlipperKioskTabCountSensor(KlipperKioskEntity, SensorEntity):
    """Sensor reporting the number of configured tabs."""

    _attr_translation_key = "tab_count"
    _attr_icon = "mdi:tab"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "tab_count")

    @property
    def native_value(self) -> int:
        """Return the count of tabs."""
        return len(self.coordinator.data.status.tabs)


class KlipperKioskDeviceIpSensor(KlipperKioskEntity, SensorEntity):
    """Diagnostic sensor reporting the tablet's LAN IP address."""

    _attr_translation_key = "device_ip"
    _attr_icon = "mdi:ip-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "device_ip")

    @property
    def native_value(self) -> str | None:
        """Return the device IP reported by the tablet."""
        return self.coordinator.data.status.device_ip

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the remote API port."""
        return {"port": self.coordinator.data.status.port}

