"""Remote platform for KlipperKiosk IR blaster."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import KlipperKioskError
from .coordinator import KlipperKioskConfigEntry, KlipperKioskCoordinator
from .entity import KlipperKioskEntity
from .ir import IrFormatError, parse_inline_ir_command


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KlipperKioskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KlipperKiosk remote entity."""
    async_add_entities([KlipperKioskRemote(entry.runtime_data)])


class KlipperKioskRemote(KlipperKioskEntity, RemoteEntity):
    """Home Assistant remote entity backed by the tablet's built-in IR blaster."""

    _attr_translation_key = "ir_remote"
    _attr_icon = "mdi:remote"
    _attr_supported_features = RemoteEntityFeature.DELETE_COMMAND

    def __init__(self, coordinator: KlipperKioskCoordinator) -> None:
        super().__init__(coordinator, "ir_remote")
        self._attr_is_on = True
        self._last_command: str | None = None

    @property
    def available(self) -> bool:
        """Available only when the tablet is reachable and has an IR emitter."""
        return (
            super().available
            and self.coordinator.data.ir is not None
            and self.coordinator.data.ir.has_ir_emitter
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose IR capabilities, saved commands, and last transmitted command."""
        attrs: dict[str, Any] = {
            "saved_commands": self.coordinator.ir_store.list_commands(),
        }
        if self.coordinator.data.ir is not None:
            attrs["carrier_frequencies"] = self.coordinator.data.ir.carrier_frequencies
        if self._last_command is not None:
            attrs["last_command"] = self._last_command
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the IR remote entity."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the IR remote entity."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more IR commands.

        Each command can be either:
        - A saved command name (saved via ``klipperkiosk.save_ir_command``)
        - An inline encoded command:
          - ``pronto:0000 006D ...`` (or raw Pronto Hex starting with ``0000 ``)
          - ``b64:<broadlink_base64>`` (Broadlink / SmartIR Base64)
          - ``nec:0x20DF10EF`` (32-bit NEC hex)
          - ``raw:9000,4500,560,...`` or ``raw:38000:9000,4500,560,...``
        """
        if not self._attr_is_on:
            raise HomeAssistantError(
                "IR remote is turned off. Turn it on before sending commands."
            )

        device: str | None = kwargs.get(ATTR_DEVICE)
        num_repeats = max(1, min(10, int(kwargs.get(ATTR_NUM_REPEATS, 1))))
        delay_secs = float(kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS))
        repeat_delay_ms = max(0, min(2000, round(delay_secs * 1000)))

        commands = list(command)
        for index, cmd in enumerate(commands):
            cmd_str = str(cmd).strip()
            payload = self.coordinator.ir_store.get_command(cmd_str, device=device)
            if payload is None:
                try:
                    payload = parse_inline_ir_command(cmd_str)
                except IrFormatError as err:
                    raise ServiceValidationError(str(err)) from err

            if payload is None:
                scope = f" for device '{device}'" if device else ""
                raise ServiceValidationError(
                    f"Unknown IR command '{cmd_str}'{scope}. Save it first with "
                    "klipperkiosk.save_ir_command or pass an inline code "
                    "(pronto:..., b64:..., nec:..., or raw:...)."
                )

            try:
                await self.coordinator.client.async_transmit_ir(
                    pattern=payload.pattern,
                    frequency=payload.frequency,
                    pronto_hex=payload.pronto_hex,
                    repeat=num_repeats,
                    repeat_delay_ms=repeat_delay_ms,
                )
            except KlipperKioskError as err:
                raise HomeAssistantError(
                    f"Failed to transmit IR command '{cmd_str}': {err}"
                ) from err

            self._last_command = f"{device}:{cmd_str}" if device else cmd_str

            if index < len(commands) - 1 and delay_secs > 0:
                await asyncio.sleep(delay_secs)

        self.async_write_ha_state()

    async def async_delete_command(self, **kwargs: Any) -> None:
        """Delete one or more saved IR commands."""
        device: str | None = kwargs.get(ATTR_DEVICE)
        commands = kwargs.get(ATTR_COMMAND, [])
        if isinstance(commands, str):
            commands = [commands]

        removed_any = False
        for cmd in commands:
            if await self.coordinator.ir_store.async_delete_command(
                str(cmd), device=device
            ):
                removed_any = True

        if not removed_any:
            raise ServiceValidationError(
                "No matching saved IR command was found to delete."
            )
        self.async_write_ha_state()
