"""Diagnostics support for KlipperKiosk."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PIN
from .coordinator import KlipperKioskConfigEntry

TO_REDACT = {CONF_PIN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KlipperKioskConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a KlipperKiosk config entry."""
    coordinator = entry.runtime_data
    status = coordinator.data.status if coordinator.data else None
    ir = coordinator.data.ir if coordinator.data else None

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "status": (
            {
                "active_tab_id": status.active_tab_id,
                "tabs": [tab.to_dict() for tab in status.tabs],
                "kiosk_locked": status.kiosk_locked,
                "lock_task_mode": status.lock_task_mode,
                "device_ip": status.device_ip,
                "port": status.port,
            }
            if status
            else None
        ),
        "ir": (
            {
                "has_ir_emitter": ir.has_ir_emitter,
                "carrier_frequencies": ir.carrier_frequencies,
            }
            if ir
            else None
        ),
    }

