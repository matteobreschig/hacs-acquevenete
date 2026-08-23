"""Coordinator: polls the API and backfills long-term statistics."""
from __future__ import annotations

import logging

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AcquaveneteApiError,
    AcquaveneteAuthError,
    AcquaveneteClient,
    DailyReading,
)
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AcquaveneteCoordinator(DataUpdateCoordinator[dict]):
    """Fetch daily readings and expose the latest index + full series."""

    def __init__(self, hass: HomeAssistant, client: AcquaveneteClient, supply_no: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{supply_no}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.supply_no = supply_no
        self._statistic_id = f"{DOMAIN}:{_slug(supply_no)}_consumption"

    async def _async_update_data(self) -> dict:
        try:
            readings = await self.client.async_get_daily_readings()
        except AcquaveneteAuthError as err:
            # Signals HA to start a reauth flow (token/GUID expired).
            from homeassistant.exceptions import ConfigEntryAuthFailed

            raise ConfigEntryAuthFailed(str(err)) from err
        except AcquaveneteApiError as err:
            raise UpdateFailed(str(err)) from err

        if not readings:
            raise UpdateFailed("No readings returned by the API")

        latest = readings[-1]

        # Consumption of the most recent available day = delta vs the previous day.
        # (The smart-meter feed can lag a day or two, so this is "last available day".)
        prev = readings[-2] if len(readings) >= 2 else None
        if prev is None:
            daily_consumption = latest.value
        else:
            daily_consumption = latest.value - prev.value
            if daily_consumption < 0:  # meter reset -> new counter starts near 0
                daily_consumption = latest.value

        # Keep long-term statistics in sync (history + latest) for the Energy dashboard.
        try:
            await self._async_import_statistics(readings)
        except Exception:  # noqa: BLE001 - never let stats break the sensor
            _LOGGER.exception("Failed to import Acquevenete statistics")

        return {
            "latest_value": latest.value,
            "latest_date": latest.date,
            "daily_consumption": daily_consumption,
            "daily_consumption_date": latest.date,
            "meter_serial": latest.meter_serial,
            "statistic_id": self._statistic_id,
            "count": len(readings),
        }

    async def _async_import_statistics(self, readings: list[DailyReading]) -> None:
        """Turn cumulative daily indices into a running consumption sum."""
        stats: list[StatisticData] = []
        running = 0.0
        prev: float | None = None

        for r in readings:
            start = dt_util.parse_datetime(r.date)
            if start is None:
                continue
            if start.tzinfo is None:
                start = start.replace(tzinfo=dt_util.UTC)
            start = start.astimezone(dt_util.UTC).replace(minute=0, second=0, microsecond=0)

            if prev is None:
                delta = 0.0
            else:
                delta = r.value - prev
                if delta < 0:  # meter replacement / rollover -> new counter from ~0
                    delta = max(r.value, 0.0)
            running += max(delta, 0.0)
            prev = r.value

            stats.append(StatisticData(start=start, state=r.value, sum=running))

        if not stats:
            return

        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"Acquevenete {self.supply_no} consumption",
            source=DOMAIN,
            statistic_id=self._statistic_id,
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        async_add_external_statistics(self.hass, metadata, stats)


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value.lower())
