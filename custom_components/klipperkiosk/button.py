"""Button platform for KlipperKiosk."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up KlipperKiosk button entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            KlipperKioskReloadButton(coordinator),
            KlipperKioskResetTabsButton(coordinator),
        ]
    )


class KlipperKioskReloadButton(KlipperKioskEntity, ButtonEntity):
    """Button to re-resolve DNS/mDNS and reload the active tab."""

    _attr_translation_key = "reload"
    _attr_icon = "mdi:reload"

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "reload")

    async def async_press(self) -> None:
        """Reload the active tab on the tablet."""
        try:
            await self.coordinator.client.async_reload()
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to reload active tab: {err}") from err
        await self.coordinator.async_request_refresh()


class KlipperKioskResetTabsButton(KlipperKioskEntity, ButtonEntity):
    """Button to reset tabs to bundled defaults."""

    _attr_translation_key = "reset_tabs"
    _attr_icon = "mdi:restore"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "reset_tabs")

    async def async_press(self) -> None:
        """Reset all tabs to default configuration."""
        try:
            await self.coordinator.client.async_reset_tabs()
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to reset tabs: {err}") from err
        await self.coordinator.async_request_refresh()

