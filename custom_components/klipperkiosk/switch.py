"""Switch platform for KlipperKiosk."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import KlipperKioskError
from .coordinator import KlipperKioskConfigEntry, KlipperKioskCoordinator
from .entity import KlipperKioskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KlipperKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KlipperKiosk switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            KlipperKioskControlsLockSwitch(coordinator),
            KlipperKioskLockTaskModeSwitch(coordinator),
        ]
    )


class KlipperKioskControlsLockSwitch(KlipperKioskEntity, SwitchEntity):
    """Switch to hide or show the top-right reload & settings controls."""

    _attr_translation_key = "kiosk_locked"
    _attr_icon = "mdi:lock-outline"

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "kiosk_locked")

    @property
    def is_on(self) -> bool:
        """Return True if top-right controls are hidden (locked)."""
        return self.coordinator.data.status.kiosk_locked

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Hide top-right controls."""
        try:
            await self.coordinator.client.async_set_controls_locked(True)
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to hide kiosk controls: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Show top-right controls."""
        try:
            await self.coordinator.client.async_set_controls_locked(False)
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to show kiosk controls: {err}") from err
        await self.coordinator.async_request_refresh()


class KlipperKioskLockTaskModeSwitch(KlipperKioskEntity, SwitchEntity):
    """Switch to enter or exit Android Device Owner Lock Task Mode."""

    _attr_translation_key = "lock_task_mode"
    _attr_icon = "mdi:tablet-lock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "lock_task_mode")

    @property
    def is_on(self) -> bool:
        """Return True if Android Lock Task Mode is active."""
        return self.coordinator.data.status.lock_task_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enter Android Lock Task Mode."""
        try:
            await self.coordinator.client.async_enter_lock_task_mode()
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to enter Lock Task Mode: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Exit Android Lock Task Mode."""
        try:
            await self.coordinator.client.async_exit_lock_task_mode()
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to exit Lock Task Mode: {err}") from err
        await self.coordinator.async_request_refresh()

