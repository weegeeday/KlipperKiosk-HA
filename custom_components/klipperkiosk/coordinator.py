"""DataUpdateCoordinator for KlipperKiosk."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IrCapabilities,
    KioskStatus,
    KlipperKioskApiClient,
    KlipperKioskApiError,
    KlipperKioskAuthError,
    KlipperKioskError,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .ir_store import KlipperKioskIrStore

_LOGGER = logging.getLogger(__name__)

type KlipperKioskConfigEntry = ConfigEntry[KlipperKioskCoordinator]


@dataclass(slots=True)
class KlipperKioskData:
    """Combined data held by the KlipperKiosk coordinator."""

    status: KioskStatus
    ir: IrCapabilities | None = None


class KlipperKioskCoordinator(DataUpdateCoordinator[KlipperKioskData]):
    """Coordinator to poll status and capabilities from a KlipperKiosk tablet."""

    config_entry: KlipperKioskConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KlipperKioskConfigEntry,
        client: KlipperKioskApiClient,
        ir_store: KlipperKioskIrStore,
    ) -> None:
        self.client = client
        self.ir_store = ir_store
        self._ir_capabilities: IrCapabilities | None = None
        self._ir_checked = False

        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.title}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> KlipperKioskData:
        """Fetch latest status (and IR capabilities once) from the tablet."""
        try:
            status = await self.client.async_get_status()
            if not self._ir_checked:
                try:
                    self._ir_capabilities = await self.client.async_get_ir_capabilities()
                except KlipperKioskApiError as err:
                    _LOGGER.debug("IR capabilities endpoint unavailable: %s", err)
                    self._ir_capabilities = None
                self._ir_checked = True
            return KlipperKioskData(status=status, ir=self._ir_capabilities)
        except KlipperKioskAuthError as err:
            raise ConfigEntryAuthFailed(
                "Invalid KlipperKiosk PIN; please re-authenticate."
            ) from err
        except KlipperKioskError as err:
            raise UpdateFailed(f"Error communicating with KlipperKiosk: {err}") from err
