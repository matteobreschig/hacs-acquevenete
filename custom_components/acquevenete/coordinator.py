"""Coordinator: polls the API and backfills the sensor's long-term statistics."""
from __future__ import annotations

import logging

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData

try:  # HA 2025.10+: metadata must declare mean_type and unit_class
    from homeassistant.components.recorder.models import StatisticMeanType
    from homeassistant.util.unit_conversion import VolumeConverter

    _EXTRA_METADATA = {
        "mean_type": StatisticMeanType.NONE,
        "unit_class": VolumeConverter.UNIT_CLASS,
    }
    _COST_EXTRA_METADATA = {"mean_type": StatisticMeanType.NONE, "unit_class": None}
except ImportError:  # older Home Assistant releases
    _EXTRA_METADATA = {}
    _COST_EXTRA_METADATA = {}
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from .api import AcquaveneteApiError, AcquaveneteAuthError, AcquaveneteClient
from .const import CONF_PRICE, CONF_PRICE_ENTITY, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AcquaveneteCoordinator(DataUpdateCoordinator[dict]):
    """Fetch daily readings, expose the latest index, and backfill statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AcquaveneteClient,
        supply_no: str,
        entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{supply_no}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.supply_no = supply_no
        self.entry = entry
        self.readings: list = []

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

        self.readings = readings
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

        return {
            "latest_value": latest.value,
            "latest_date": latest.date,
            "daily_consumption": daily_consumption,
            "daily_consumption_date": latest.date,
            "meter_serial": latest.meter_serial,
            "count": len(readings),
        }

    @callback
    def import_statistics(self, statistic_id: str) -> None:
        """Attach the full daily history to the sensor's own statistic_id.

        `statistic_id` is the sensor's entity_id, so the history lives ON the
        entity: it can be used directly by the Energy dashboard AND as a
        utility_meter source, without any external/orphan statistic.
        """
        if not self.readings:
            return
        try:
            stats = self._build_statistics()
            if not stats:
                return
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=None,  # inherit the entity's friendly name
                source="recorder",  # internal statistics attached to the entity
                statistic_id=statistic_id,
                unit_of_measurement=UnitOfVolume.CUBIC_METERS,
                **_EXTRA_METADATA,
            )
            async_import_statistics(self.hass, metadata, stats)
        except Exception:  # noqa: BLE001 - never let stats break the entity
            _LOGGER.exception("Failed to import Acquevenete statistics")

    @property
    def cost_statistic_id(self) -> str:
        """External statistic holding the cumulative cost, for the Energy dashboard."""
        return f"{DOMAIN}:{slugify(self.supply_no)}_cost"

    @property
    def price_entity(self) -> str | None:
        return (self.entry.options if self.entry else {}).get(CONF_PRICE_ENTITY) or None

    def _price(self) -> float | None:
        """Price per m3 from the configured entity, else the fixed option."""
        options = self.entry.options if self.entry else {}
        if self.price_entity:
            state = self.hass.states.get(self.price_entity)
            try:
                return float(state.state) if state else None
            except (TypeError, ValueError):
                return None
        price = options.get(CONF_PRICE)
        return float(price) if price not in (None, "") else None

    @callback
    def import_cost_statistics(self) -> None:
        """Write the cumulative cost (consumption x current price) as a statistic.

        The Energy dashboard's own cost tracking only sees live state changes,
        which never happen for back-filled readings, so it would always show 0.
        Pointing the water source's "cost statistic" here fixes that. The current
        price is applied to the whole history.
        """
        price = self._price()
        if price is None or not self.readings:
            return
        try:
            stats = [
                StatisticData(start=s["start"], sum=round(s["sum"] * price, 4))
                for s in self._build_statistics()
            ]
            if not stats:
                return
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"Acquevenete {self.supply_no} cost",
                source=DOMAIN,
                statistic_id=self.cost_statistic_id,
                unit_of_measurement=self.hass.config.currency,
                **_COST_EXTRA_METADATA,
            )
            async_add_external_statistics(self.hass, metadata, stats)
        except Exception:  # noqa: BLE001 - never let stats break the entity
            _LOGGER.exception("Failed to import Acquevenete cost statistics")

    def _build_statistics(self) -> list[StatisticData]:
        """Turn cumulative daily indices into a running consumption sum."""
        stats: list[StatisticData] = []
        running = 0.0
        prev: float | None = None

        for r in self.readings:
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

        return stats
