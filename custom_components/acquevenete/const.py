"""Constants for the Acquevenete integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "acquevenete"

# Config keys
CONF_TOKEN = "token"          # the account GUID that appears in the API URLs
CONF_SUPPLY = "supply_no"     # e.g. "12345678-1"
CONF_PAGE = "page"            # trailing segment of the week-chart URL

DEFAULT_PAGE = "1"
DEFAULT_NAME = "Acquevenete"

BASE_URL = "https://sol.acquevenete.it/webapi/api/v1"

# Poll every 6h: the source data only changes ~once per day.
SCAN_INTERVAL = timedelta(hours=6)

# Reading types coming from the smart meter daily telemetry.
SMART_METER_TYPE = "SMART METERING"

ATTR_LAST_READING_DATE = "last_reading_date"
ATTR_METER_SERIAL = "meter_serial"
ATTR_SUPPLY_NO = "supply_no"
