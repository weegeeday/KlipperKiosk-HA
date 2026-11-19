"""Binary sensor platform for KlipperKiosk."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up KlipperKiosk binary sensor entities."""
    async_add_entities([KlipperKioskIrEmitterBinarySensor(entry.runtime_data)])


class KlipperKioskIrEmitterBinarySensor(KlipperKioskEntity, BinarySensorEntity):
    """Diagnostic binary sensor reporting whether the tablet has an IR emitter."""

    _attr_translation_key = "ir_emitter"
    _attr_icon = "mdi:remote"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "ir_emitter")

    @property
    def available(self) -> bool:
        """Available when coordinator is up and IR capability was queried."""
        return super().available and self.coordinator.data.ir is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if the tablet has a built-in IR emitter."""
        if self.coordinator.data.ir is None:
            return None
        return self.coordinator.data.ir.has_ir_emitter

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return supported carrier frequency ranges in Hz."""
        if self.coordinator.data.ir is None:
            return {}
        return {
            "carrier_frequencies": self.coordinator.data.ir.carrier_frequencies,
        }

