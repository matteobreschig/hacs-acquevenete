"""Constants for the Acquevenete integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "acquevenete"

# Config keys
CONF_USERNAME = "username"    # portal login e-mail
CONF_PASSWORD = "password"    # portal password
CONF_TOKEN = "token"          # legacy: account GUID (now auto-obtained via login)
CONF_SUPPLY = "supply_no"     # e.g. "12345678-1"
CONF_PAGE = "page"            # trailing segment of the week-chart URL

DEFAULT_PAGE = "1"
DEFAULT_NAME = "Acquevenete"

BASE_URL = "https://sol.acquevenete.it/webapi/api/v1"
LOGIN_URL = "https://sol.acquevenete.it/login.aspx"
HOME_URL = "https://sol.acquevenete.it/index.aspx"

# Options
CONF_PRICE = "price"                # fixed water price per m3
CONF_PRICE_ENTITY = "price_entity"  # or an entity holding the price per m3

# Seconds before a portal request is abandoned.
REQUEST_TIMEOUT = 30

# Poll every 6h: the source data only changes ~once per day.
SCAN_INTERVAL = timedelta(hours=6)

# Reading types coming from the smart meter daily telemetry.
SMART_METER_TYPE = "SMART METERING"

ATTR_LAST_READING_DATE = "last_reading_date"
ATTR_METER_SERIAL = "meter_serial"
ATTR_SUPPLY_NO = "supply_no"

SERVICE_IMPORT_HISTORY = "import_history"
ATTR_STATISTIC_ID = "statistic_id"
