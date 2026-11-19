"""Select platform for KlipperKiosk (active tab selector)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import KioskTab, KlipperKioskError
from .coordinator import KlipperKioskConfigEntry, KlipperKioskCoordinator
from .entity import KlipperKioskEntity


def _build_tab_option_map(tabs: list[KioskTab]) -> dict[str, KioskTab]:
    """Build an ordered mapping of display label -> KioskTab, disambiguating duplicates."""
    base_labels = [tab.title or tab.url or tab.id for tab in tabs]
    counts = Counter(base_labels)
    mapping: dict[str, KioskTab] = {}
    for tab, base in zip(tabs, base_labels, strict=True):
        label = f"{base} ({tab.id})" if counts[base] > 1 else base
        mapping[label] = tab
    return mapping


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KlipperKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KlipperKiosk select entities."""
    async_add_entities([KlipperKioskActiveTabSelect(entry.runtime_data)])


class KlipperKioskActiveTabSelect(KlipperKioskEntity, SelectEntity):
    """Select entity to view and switch the active kiosk tab."""

    _attr_translation_key = "active_tab"
    _attr_icon = "mdi:tab"

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "active_tab")

    @property
    def _option_map(self) -> dict[str, KioskTab]:
        return _build_tab_option_map(self.coordinator.data.status.tabs)

    @property
    def options(self) -> list[str]:
        """Return the list of available tab labels."""
        return list(self._option_map.keys())

    @property
    def current_option(self) -> str | None:
        """Return the label of the currently active tab."""
        active_id = self.coordinator.data.status.active_tab_id
        if not active_id:
            return None
        for label, tab in self._option_map.items():
            if tab.id == active_id:
                return label
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose tab IDs and URLs for automations and templates."""
        status = self.coordinator.data.status
        active_tab = status.active_tab
        attrs: dict[str, Any] = {
            "active_tab_id": status.active_tab_id,
            "tabs": [tab.to_dict() for tab in status.tabs],
        }
        if active_tab:
            attrs["active_tab_url"] = active_tab.url
            if active_tab.resolved_url:
                attrs["active_tab_resolved_url"] = active_tab.resolved_url
        return attrs

    async def async_select_option(self, option: str) -> None:
        """Switch the tablet to the chosen tab."""
        tab = self._option_map.get(option)
        if tab is None:
            raise HomeAssistantError(f"Unknown tab option: {option}")
        try:
            await self.coordinator.client.async_activate_tab(tab.id)
        except KlipperKioskError as err:
            raise HomeAssistantError(f"Failed to activate tab '{option}': {err}") from err
        await self.coordinator.async_request_refresh()

