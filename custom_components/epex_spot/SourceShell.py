"""SourceShell"""

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt

from custom_components.epex_spot.const import (
    CONF_DURATION,
    CONF_EARLIEST_START_POST,
    CONF_EARLIEST_START_TIME,
    CONF_LATEST_END_POST,
    CONF_LATEST_END_TIME,
    CONF_MARKET_AREA,
    CONF_SOURCE,
    CONF_SOURCE_AWATTAR,
    CONF_SOURCE_ENERGYFORECAST,
    CONF_SOURCE_ENTSOE,
    CONF_SOURCE_ENERGYCHARTS,
    CONF_SOURCE_SMARD_DE,
    CONF_SOURCE_SMARTENERGY,
    CONF_SOURCE_TIBBER,
    CONF_SOURCE_HOFER_GRUENSTROM,
    CONF_SURCHARGE_ABS,
    CONF_SURCHARGE_PERC,
    CONF_TAX,
    CONF_GRIDSURCHARGE_STANDARD,
    CONF_GRIDSURCHARGE_SLOT1,
    CONF_GRIDMONTHS_SLOT1,
    CONF_GRIDTIMESTART_SLOT1,
    CONF_GRIDTIMEEND_SLOT1,
    CONF_GRIDSURCHARGE_SLOT2,
    CONF_GRIDMONTHS_SLOT2,
    CONF_GRIDTIMESTART_SLOT2,
    CONF_GRIDTIMEEND_SLOT2,
    CONF_GRIDSURCHARGE_SLOT3,
    CONF_GRIDMONTHS_SLOT3,
    CONF_GRIDTIMESTART_SLOT3,
    CONF_GRIDTIMEEND_SLOT3,
    CONF_GRIDSURCHARGE_SLOT4,
    CONF_GRIDMONTHS_SLOT4,
    CONF_GRIDTIMESTART_SLOT4,
    CONF_GRIDTIMEEND_SLOT4,
    CONF_TOKEN,
    DEFAULT_DURATION,
    DEFAULT_SURCHARGE_ABS,
    DEFAULT_SURCHARGE_PERC,
    DEFAULT_TAX,
    EMPTY_EXTREME_PRICE_INTERVAL_RESP,
)
from custom_components.epex_spot.EPEXSpot import (
    SMARD,
    Awattar,
    Energyforecast,
    Tibber,
    smartENERGY,
    ENTSOE,
    EnergyCharts,
    HoferGruenstrom,
)
from .extreme_price_interval import find_extreme_price_interval, get_start_times

_LOGGER = logging.getLogger(__name__)


class SourceShell:
    def __init__(self, config_entry: ConfigEntry, session: aiohttp.ClientSession):
        self._config_entry = config_entry
        self.marketdata_total = []
        self._marketdata_now = None
        self._sorted_marketdata_today = []
        self._sorted_total_price_today = []
        self._cheapest_sorted_marketdata_today = None
        self._most_expensive_sorted_marketdata_today = None

        # create source object
        if config_entry.data[CONF_SOURCE] == CONF_SOURCE_AWATTAR:
            self._source = Awattar.Awattar(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_SMARD_DE:
            self._source = SMARD.SMARD(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_SMARTENERGY:
            self._source = smartENERGY.smartENERGY(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_TIBBER:
            self._source = Tibber.Tibber(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                token=self._config_entry.data[CONF_TOKEN],
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_ENERGYFORECAST:
            self._source = Energyforecast.Energyforecast(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                token=self._config_entry.data[CONF_TOKEN],
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_ENTSOE:
            self._source = ENTSOE.EntsoeTransparency(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                token=self._config_entry.data[CONF_TOKEN],
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_ENERGYCHARTS:
            self._source = EnergyCharts.EnergyCharts(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                session=session,
            )
        elif config_entry.data[CONF_SOURCE] == CONF_SOURCE_HOFER_GRUENSTROM:
            self._source = HoferGruenstrom.HoferGruenstrom(
                market_area=config_entry.data[CONF_MARKET_AREA],
                duration=config_entry.options.get(CONF_DURATION, DEFAULT_DURATION),
                session=session,
            )
        else:
            raise ValueError(f"Unsupported source: {config_entry.data[CONF_SOURCE]}")

    @property
    def unique_id(self):
        return self._config_entry.unique_id

    @property
    def name(self):
        return self._source.name

    @property
    def market_area(self):
        return self._source.market_area

    @property
    def duration(self):
        return self._source.duration

    @property
    def currency(self):
        return self._source.currency

    @property
    def marketdata(self):
        return self._source.marketdata

    @property
    def marketdata_now(self):
        return self._marketdata_now

    @property
    def sorted_marketdata_today(self):
        """Sorted by price."""
        return self._sorted_marketdata_today

    async def fetch(self, *args: Any):
        await self._source.fetch()

    def update_time(self):
        if (len(self.marketdata)) == 0:
            self._marketdata_now = None
            self._sorted_marketdata_today = []
            self._sorted_total_price_today = []
            self.marketdata_total = []
            return

        now = dt.now()

        # find current entry in marketdata list
        try:
            self._marketdata_now = next(
                filter(
                    lambda e: e.start_time <= now and e.end_time > now, self.marketdata
                )
            )
        except StopIteration:
            _LOGGER.error(f"no data found for {self._source}")
            self._marketdata_now = None
            self._sorted_marketdata_today = []
            self.marketdata_total = []

        # get list of entries for today
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        sorted_marketdata_today = filter(
            lambda e: e.start_time >= start_of_day and e.end_time <= end_of_day,
            self.marketdata,
        )
        sorted_sorted_marketdata_today = sorted(
            sorted_marketdata_today, key=lambda e: e.market_price_per_kwh
        )
        self._sorted_marketdata_today = sorted_sorted_marketdata_today

        sorted_total_prices = []
        for entry in self._sorted_marketdata_today:
            total_price = self.to_total_price(
                entry.market_price_per_kwh,
                entry.start_time
            )
            sorted_total_prices.append(total_price)

        self._sorted_total_price_today = sorted_total_prices
        
        self.marketdata_total = []
        for entry in self.marketdata:
            total_price = self.to_total_price(
                entry.market_price_per_kwh, 
                entry.start_time
            )
            self.marketdata_total.append(total_price)

    def get_grid_surcharge(self, dt):
        if dt is None:
            return float(self.options.get(CONF_GRIDSURCHARGE_STANDARD, 0.0))

        month = dt.month
        current_time = dt.strftime("%H:%M")

        for i in range(1, 5):
            surcharge_key = f"grid_surcharge_slot{i}"
            months_key = f"grid_months_slot{i}"
            start_key = f"grid_time_start_slot{i}"
            end_key = f"grid_time_end_slot{i}"

            if self.is_slot_active(surcharge_key, months_key, start_key, end_key, month, current_time):
                return float(self.options.get(surcharge_key, 0.0))

        return float(self.options.get(CONF_GRIDSURCHARGE_STANDARD, 0.0))


    def is_slot_active(self, surcharge_key, months_key, start_key, end_key, current_month, current_time):
        if self.options.get(surcharge_key) is None:
            return False

        months_str = str(self.options.get(months_key, "")).strip()
        if months_str:
            try:
                allowed_months = {int(m.strip()) for m in months_str.split(",") if m.strip().isdigit()}
                if current_month not in allowed_months:
                    return False
            except (ValueError, TypeError):
                return False

        start_time = str(self.options.get(start_key, "00:00")).strip()
        end_time = str(self.options.get(end_key, "23:59")).strip()

        return start_time <= current_time <= end_time
    
    def to_total_price(self, market_price_per_kwh, dt=None):
        total_price = market_price_per_kwh

        # Standard calculation for other cases
        if "Tibber API" not in self.name:
            # Retrieve tax and surcharge values from config
            surcharge_abs = self._config_entry.options.get(
                CONF_SURCHARGE_ABS, DEFAULT_SURCHARGE_ABS
            )
            tax = self._config_entry.options.get(CONF_TAX, DEFAULT_TAX)

            surcharge_pct = self._config_entry.options.get(
                CONF_SURCHARGE_PERC, DEFAULT_SURCHARGE_PERC
            )

            grid_surcharge = self.get_grid_surcharge(dt)
            
            total_price = total_price + abs(total_price) * surcharge_pct / 100
            total_price += surcharge_abs
            total_price += grid_surcharge
            total_price *= 1 + (tax / 100.0)

        return round(total_price, 6)

    def find_extreme_price_interval(self, call_data, cmp):
        duration: timedelta = call_data[CONF_DURATION]

        start_times = get_start_times(
            marketdata=self.marketdata,
            earliest_start_time=call_data.get(CONF_EARLIEST_START_TIME),
            earliest_start_post=call_data.get(CONF_EARLIEST_START_POST),
            latest_end_time=call_data.get(CONF_LATEST_END_TIME),
            latest_end_post=call_data.get(CONF_LATEST_END_POST),
            latest_market_datetime=self.marketdata[-1].end_time,
            duration=duration,
        )

        result = find_extreme_price_interval(
            self.marketdata, start_times, duration, cmp
        )

        if result is None:
            return EMPTY_EXTREME_PRICE_INTERVAL_RESP

        return {
            "start": result["start"],
            "end": result["start"] + duration,
            "market_price_per_kwh": round(result["market_price_per_hour"], 6),
            "total_price_per_kwh": self.to_total_price(result["market_price_per_hour"]),
        }
