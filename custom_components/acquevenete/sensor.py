"""Sensor platform for Acquevenete."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_LAST_READING_DATE,
    ATTR_METER_SERIAL,
    ATTR_SUPPLY_NO,
    DOMAIN,
)
from .coordinator import AcquaveneteCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AcquaveneteCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AcquaveneteMeterSensor(coordinator, entry),
            AcquaveneteDailyConsumptionSensor(coordinator, entry),
            AcquaveneteLastReadingSensor(coordinator, entry),
        ]
    )


class AcquaveneteMeterSensor(CoordinatorEntity[AcquaveneteCoordinator], SensorEntity):
    """Cumulative water meter index (m3), updated ~daily."""

    _attr_has_entity_name = True
    _attr_name = "Water meter"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS

    def __init__(self, coordinator: AcquaveneteCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._supply_no = coordinator.supply_no
        self._attr_unique_id = f"{DOMAIN}_{coordinator.supply_no}_meter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.supply_no)},
            name=f"Acquevenete {coordinator.supply_no}",
            manufacturer="Acquevenete",
            model="Smart water meter",
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("latest_value")

    async def async_added_to_hass(self) -> None:
        """Attach the historical statistics to this entity once its id is known."""
        await super().async_added_to_hass()
        self.coordinator.import_statistics(self.entity_id)
        self.coordinator.import_cost_statistics()

    def _handle_coordinator_update(self) -> None:
        # Keep statistics in sync (history + latest) on every refresh.
        self.coordinator.import_statistics(self.entity_id)
        self.coordinator.import_cost_statistics()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            ATTR_SUPPLY_NO: self._supply_no,
            ATTR_LAST_READING_DATE: data.get("latest_date"),
            ATTR_METER_SERIAL: data.get("meter_serial"),
        }


class AcquaveneteDailyConsumptionSensor(
    CoordinatorEntity[AcquaveneteCoordinator], SensorEntity
):
    """Consumption of the most recent available day (m3).

    No WATER device_class here on purpose: this is a per-day delta, not an
    accumulating total, so we keep it a plain measurement to avoid statistics
    validation warnings. The reference day is exposed as an attribute.
    """

    _attr_has_entity_name = True
    _attr_name = "Daily consumption"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water"

    def __init__(self, coordinator: AcquaveneteCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._supply_no = coordinator.supply_no
        self._attr_unique_id = f"{DOMAIN}_{coordinator.supply_no}_daily"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.supply_no)},
            name=f"Acquevenete {coordinator.supply_no}",
            manufacturer="Acquevenete",
            model="Smart water meter",
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("daily_consumption")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            ATTR_SUPPLY_NO: self._supply_no,
            "reference_date": data.get("daily_consumption_date"),
        }


class AcquaveneteLastReadingSensor(
    CoordinatorEntity[AcquaveneteCoordinator], SensorEntity
):
    """Date of the most recent reading published by the portal.

    The smart meter feed lags and sometimes stalls for days: this makes it easy
    to alert when no new reading has arrived for a while.
    """

    _attr_has_entity_name = True
    _attr_name = "Last reading"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AcquaveneteCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.supply_no}_last_reading"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.supply_no)},
            name=f"Acquevenete {coordinator.supply_no}",
            manufacturer="Acquevenete",
            model="Smart water meter",
        )

    @property
    def native_value(self):
        date = (self.coordinator.data or {}).get("latest_date")
        parsed = dt_util.parse_datetime(date) if date else None
        if parsed is not None and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.UTC)
        return parsed
