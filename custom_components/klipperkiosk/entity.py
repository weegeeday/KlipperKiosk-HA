"""Base entity for the KlipperKiosk integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KlipperKioskCoordinator


class KlipperKioskEntity(CoordinatorEntity[KlipperKioskCoordinator]):
    """Base entity linked to a KlipperKiosk tablet device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KlipperKioskCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="KlipperKiosk",
            model="Android Kiosk Tablet",
            configuration_url=coordinator.client.base_url,
        )

