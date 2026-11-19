"""The KlipperKiosk Home Assistant integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import KlipperKioskApiClient, KlipperKioskError
from .const import (
    ATTR_ACTIVATE,
    ATTR_FREQUENCY,
    ATTR_IDS,
    ATTR_PATTERN,
    ATTR_PIN,
    ATTR_PRONTO_HEX,
    ATTR_REPEAT,
    ATTR_REPEAT_DELAY_MS,
    ATTR_TAB_ID,
    ATTR_TITLE,
    ATTR_URL,
    CONF_PIN,
    DOMAIN,
    SERVICE_ACTIVATE_TAB,
    SERVICE_ADD_TAB,
    SERVICE_DELETE_TAB,
    SERVICE_NAVIGATE,
    SERVICE_REORDER_TABS,
    SERVICE_SEND_IR,
    SERVICE_SET_PIN,
    SERVICE_UPDATE_TAB,
)
from .coordinator import KlipperKioskConfigEntry, KlipperKioskCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_ADD_TAB_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_ACTIVATE, default=True): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_UPDATE_TAB_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TAB_ID): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_URL): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_DELETE_TAB_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TAB_ID): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_ACTIVATE_TAB_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TAB_ID): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_REORDER_TABS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_IDS): vol.All(cv.ensure_list, [cv.string]),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_NAVIGATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PIN): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_IR_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_PATTERN): vol.All(
            cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1))]
        ),
        vol.Optional(ATTR_FREQUENCY, default=38000): vol.All(
            vol.Coerce(int), vol.Range(min=10000, max=100000)
        ),
        vol.Optional(ATTR_PRONTO_HEX): cv.string,
        vol.Optional(ATTR_REPEAT, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10)
        ),
        vol.Optional(ATTR_REPEAT_DELAY_MS, default=100): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=2000)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _resolve_target_entries(
    hass: HomeAssistant, call: ServiceCall
) -> list[KlipperKioskConfigEntry]:
    """Resolve target KlipperKiosk config entries from a service call."""
    loaded_entries: dict[str, KlipperKioskConfigEntry] = {
        entry.entry_id: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    }

    if not loaded_entries:
        raise HomeAssistantError("No loaded KlipperKiosk devices are configured.")

    device_ids = _as_list(call.data.get(ATTR_DEVICE_ID))
    entity_ids = _as_list(call.data.get(ATTR_ENTITY_ID))
    area_ids = _as_list(call.data.get(ATTR_AREA_ID))

    if not device_ids and not entity_ids and not area_ids:
        if len(loaded_entries) == 1:
            return list(loaded_entries.values())
        raise ServiceValidationError(
            "Multiple KlipperKiosk tablets are configured; please specify a target device."
        )

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    matched_ids: set[str] = set()

    for device_id in device_ids:
        if device := dev_reg.async_get(device_id):
            for entry_id in device.config_entries:
                if entry_id in loaded_entries:
                    matched_ids.add(entry_id)

    for entity_id in entity_ids:
        if entity := ent_reg.async_get(entity_id):
            if entity.config_entry_id in loaded_entries:
                matched_ids.add(entity.config_entry_id)

    for area_id in area_ids:
        for device in dr.async_entries_for_area(dev_reg, area_id):
            for entry_id in device.config_entries:
                if entry_id in loaded_entries:
                    matched_ids.add(entry_id)

    if not matched_ids:
        raise ServiceValidationError(
            "No matching KlipperKiosk device found for the provided target."
        )

    return [loaded_entries[entry_id] for entry_id in matched_ids]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register KlipperKiosk domain services."""

    async def handle_add_tab(call: ServiceCall) -> None:
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_add_tab(
                    url=call.data[ATTR_URL],
                    title=call.data.get(ATTR_TITLE),
                    activate=call.data[ATTR_ACTIVATE],
                )
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to add tab: {err}") from err
            await coordinator.async_request_refresh()

    async def handle_update_tab(call: ServiceCall) -> None:
        title = call.data.get(ATTR_TITLE)
        url = call.data.get(ATTR_URL)
        if title is None and url is None:
            raise ServiceValidationError(
                "At least one of 'title' or 'url' must be provided."
            )
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_update_tab(
                    tab_id=call.data[ATTR_TAB_ID],
                    title=title,
                    url=url,
                )
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to update tab: {err}") from err
            await coordinator.async_request_refresh()

    async def handle_delete_tab(call: ServiceCall) -> None:
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_delete_tab(call.data[ATTR_TAB_ID])
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to delete tab: {err}") from err
            await coordinator.async_request_refresh()

    async def handle_activate_tab(call: ServiceCall) -> None:
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_activate_tab(call.data[ATTR_TAB_ID])
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to activate tab: {err}") from err
            await coordinator.async_request_refresh()

    async def handle_reorder_tabs(call: ServiceCall) -> None:
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_reorder_tabs(call.data[ATTR_IDS])
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to reorder tabs: {err}") from err
            await coordinator.async_request_refresh()

    async def handle_navigate(call: ServiceCall) -> None:
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_navigate(call.data[ATTR_URL])
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to navigate: {err}") from err

    async def handle_set_pin(call: ServiceCall) -> None:
        new_pin = call.data[ATTR_PIN].strip()
        if not new_pin:
            raise ServiceValidationError("PIN cannot be empty.")
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_set_pin(new_pin)
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to update PIN: {err}") from err
            # Persist the new PIN in the config entry so polling stays authenticated
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_PIN: new_pin}
            )

    async def handle_send_ir(call: ServiceCall) -> None:
        pattern = call.data.get(ATTR_PATTERN)
        pronto_hex = call.data.get(ATTR_PRONTO_HEX)
        if not pattern and not pronto_hex:
            raise ServiceValidationError(
                "Either 'pattern' (microseconds list) or 'pronto_hex' must be provided."
            )
        for entry in _resolve_target_entries(hass, call):
            coordinator = entry.runtime_data
            try:
                await coordinator.client.async_transmit_ir(
                    pattern=pattern,
                    frequency=call.data[ATTR_FREQUENCY],
                    pronto_hex=pronto_hex,
                    repeat=call.data[ATTR_REPEAT],
                    repeat_delay_ms=call.data[ATTR_REPEAT_DELAY_MS],
                )
            except KlipperKioskError as err:
                raise HomeAssistantError(f"Failed to transmit IR signal: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TAB, handle_add_tab, schema=SERVICE_ADD_TAB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_TAB, handle_update_tab, schema=SERVICE_UPDATE_TAB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_TAB, handle_delete_tab, schema=SERVICE_DELETE_TAB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_TAB,
        handle_activate_tab,
        schema=SERVICE_ACTIVATE_TAB_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REORDER_TABS,
        handle_reorder_tabs,
        schema=SERVICE_REORDER_TABS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NAVIGATE, handle_navigate, schema=SERVICE_NAVIGATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PIN, handle_set_pin, schema=SERVICE_SET_PIN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_IR, handle_send_ir, schema=SERVICE_SEND_IR_SCHEMA
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: KlipperKioskConfigEntry
) -> bool:
    """Set up KlipperKiosk from a config entry."""
    session = async_get_clientsession(hass)
    client = KlipperKioskApiClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        pin=entry.data[CONF_PIN],
    )
    coordinator = KlipperKioskCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: KlipperKioskConfigEntry
) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: KlipperKioskConfigEntry
) -> bool:
    """Unload a KlipperKiosk config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

