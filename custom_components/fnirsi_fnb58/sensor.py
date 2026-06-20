from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FNB58Coordinator


@dataclass(frozen=True, kw_only=True)
class FNB58SensorDescription(SensorEntityDescription):
    value_key: str


SENSORS: tuple[FNB58SensorDescription, ...] = (
    FNB58SensorDescription(
        key="voltage",
        translation_key="voltage",
        value_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
    ),
    FNB58SensorDescription(
        key="current",
        translation_key="current",
        value_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
    ),
    FNB58SensorDescription(
        key="power",
        translation_key="power",
        value_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
    ),
    FNB58SensorDescription(
        key="dp",
        translation_key="dp",
        value_key="dp",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    FNB58SensorDescription(
        key="dn",
        translation_key="dn",
        value_key="dn",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    FNB58SensorDescription(
        key="temperature",
        translation_key="temperature",
        value_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    FNB58SensorDescription(
        key="energy_wh",
        translation_key="energy_wh",
        value_key="energy_wh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=5,
    ),
    FNB58SensorDescription(
        key="capacity_ah",
        translation_key="capacity_ah",
        value_key="capacity_ah",
        native_unit_of_measurement="Ah",
        suggested_display_precision=5,
    ),
    FNB58SensorDescription(
        key="record_seconds",
        translation_key="record_seconds",
        value_key="record_seconds",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    FNB58SensorDescription(
        key="power_on_seconds",
        translation_key="power_on_seconds",
        value_key="power_on_seconds",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    # Keep this disabled by default: it tends to add noise in normal use.
    # FNB58SensorDescription(
    #     key="inferred_protocol",
    #     translation_key="inferred_protocol",
    #     value_key="inferred_protocol",
    #     entity_category=EntityCategory.DIAGNOSTIC,
    # ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FNB58Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(FNB58Sensor(coordinator, description) for description in SENSORS)


class FNB58Sensor(CoordinatorEntity[FNB58Coordinator], SensorEntity):
    entity_description: FNB58SensorDescription

    def __init__(
        self,
        coordinator: FNB58Coordinator,
        description: FNB58SensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.value_key)

    @property
    def available(self) -> bool:
        if not self.coordinator.is_available:
            return False
        if self.entity_description.value_key == "inferred_protocol":
            return self.coordinator.protocol is not None
        return self.coordinator.data is not None
