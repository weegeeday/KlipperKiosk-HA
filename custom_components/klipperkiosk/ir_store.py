"""Persistent storage for named KlipperKiosk IR commands."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .ir import IrPayload

STORAGE_VERSION = 1
DEFAULT_IR_DEVICE = "default"


class KlipperKioskIrStore:
    """Persist named IR commands per KlipperKiosk config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.ir_commands.{entry_id}"
        )
        self._devices: dict[str, dict[str, dict[str, Any]]] = {}

    async def async_load(self) -> None:
        """Load saved IR commands from disk."""
        data = await self._store.async_load()
        if isinstance(data, dict) and isinstance(data.get("devices"), dict):
            self._devices = {
                str(dev): {
                    str(cmd): dict(payload)
                    for cmd, payload in cmds.items()
                    if isinstance(payload, dict)
                }
                for dev, cmds in data["devices"].items()
                if isinstance(cmds, dict)
            }
        else:
            self._devices = {}

    async def _async_save(self) -> None:
        await self._store.async_save({"devices": self._devices})

    async def async_save_command(
        self, command: str, payload: IrPayload, device: str | None = None
    ) -> None:
        """Save or overwrite a named IR command."""
        dev_key = (device or DEFAULT_IR_DEVICE).strip() or DEFAULT_IR_DEVICE
        cmd_key = command.strip()
        self._devices.setdefault(dev_key, {})[cmd_key] = payload.to_storage_dict()
        await self._async_save()

    async def async_delete_command(
        self, command: str, device: str | None = None
    ) -> bool:
        """Delete a saved IR command; returns True if a command was removed."""
        cmd_key = command.strip()
        if device:
            dev_key = device.strip()
            cmds = self._devices.get(dev_key)
            if not cmds or cmd_key not in cmds:
                return False
            del cmds[cmd_key]
            if not cmds:
                del self._devices[dev_key]
            await self._async_save()
            return True

        # No device specified: try default first, otherwise remove from any matching device
        if DEFAULT_IR_DEVICE in self._devices and cmd_key in self._devices[DEFAULT_IR_DEVICE]:
            del self._devices[DEFAULT_IR_DEVICE][cmd_key]
            if not self._devices[DEFAULT_IR_DEVICE]:
                del self._devices[DEFAULT_IR_DEVICE]
            await self._async_save()
            return True

        removed = False
        for dev_key in list(self._devices):
            if cmd_key in self._devices[dev_key]:
                del self._devices[dev_key][cmd_key]
                if not self._devices[dev_key]:
                    del self._devices[dev_key]
                removed = True
        if removed:
            await self._async_save()
        return removed

    def get_command(
        self, command: str, device: str | None = None
    ) -> IrPayload | None:
        """Look up a saved IR command."""
        cmd_key = command.strip()
        if device:
            dev_key = device.strip()
            raw = self._devices.get(dev_key, {}).get(cmd_key)
            return IrPayload.from_storage_dict(raw) if raw else None

        # Check default device first
        raw = self._devices.get(DEFAULT_IR_DEVICE, {}).get(cmd_key)
        if raw:
            return IrPayload.from_storage_dict(raw)

        # Fallback: if command name exists uniquely in a single device, return it
        matches = [
            cmds[cmd_key]
            for cmds in self._devices.values()
            if cmd_key in cmds
        ]
        if len(matches) == 1:
            return IrPayload.from_storage_dict(matches[0])
        return None

    def list_commands(self) -> dict[str, list[str]]:
        """Return a mapping of device -> sorted list of saved command names."""
        return {
            dev: sorted(cmds.keys())
            for dev, cmds in sorted(self._devices.items())
            if cmds
        }
