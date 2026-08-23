"""Client for the (undocumented) Acquevenete self-service API.

The portal exposes per-account JSON endpoints where the account GUID is part of
the URL path (no header auth). The week-consumption-chart endpoint nests one
"SMART METERING" reading per day inside weekly buckets; those daily points are
what give us ~daily / 1 m3 resolution.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from aiohttp import ClientError, ClientSession

from .const import BASE_URL, SMART_METER_TYPE

_LOGGER = logging.getLogger(__name__)


class AcquaveneteAuthError(Exception):
    """Raised when the token/GUID looks invalid or expired."""


class AcquaveneteApiError(Exception):
    """Raised on any other API/transport failure."""


@dataclass
class DailyReading:
    """A single daily meter reading (cumulative index in m3)."""

    date: str          # ISO-8601 string, e.g. "2025-01-03T00:00:00Z"
    value: float       # meter index at that date
    meter_serial: str | None = None


class AcquaveneteClient:
    """Thin async wrapper over the endpoints we need."""

    def __init__(self, session: ClientSession, token: str, supply_no: str, page: str = "1") -> None:
        self._session = session
        self._token = token.strip()
        self._supply_no = supply_no.strip()
        self._page = str(page).strip() or "1"

    async def _get_json(self, path: str):
        url = f"{BASE_URL}/{path}"
        try:
            async with self._session.get(url) as resp:
                if resp.status in (401, 403):
                    raise AcquaveneteAuthError(f"HTTP {resp.status} for {url}")
                if resp.status != 200:
                    raise AcquaveneteApiError(f"HTTP {resp.status} for {url}")
                # The endpoint returns application/json but occasionally with a
                # charset the aiohttp guesser dislikes; force parsing.
                return await resp.json(content_type=None)
        except ClientError as err:
            raise AcquaveneteApiError(str(err)) from err

    async def async_validate(self) -> bool:
        """Cheap call used by the config flow to check token + supply."""
        data = await self.async_get_daily_readings()
        return len(data) > 0

    async def async_get_daily_readings(self) -> list[DailyReading]:
        """Fetch the week-chart and flatten it to a sorted list of daily readings."""
        payload = await self._get_json(
            f"supply-week-consumption-chart/{self._token}/{self._supply_no}/{self._page}/"
        )
        return self._flatten(payload)

    @staticmethod
    def _flatten(payload) -> list[DailyReading]:
        """Collapse the nested Highcharts structure into unique daily points.

        Structure:
          payload["data"]                -> list of yearly series
            series["data"]               -> list of weekly buckets
              bucket["readings"]         -> list of daily SMART METERING readings
        Readings overlap between adjacent buckets, so we dedupe by date.
        """
        if not isinstance(payload, dict):
            raise AcquaveneteApiError("Unexpected payload (not an object)")

        by_date: dict[str, DailyReading] = {}
        for series in payload.get("data", []) or []:
            for bucket in series.get("data", []) or []:
                for r in bucket.get("readings", []) or []:
                    date = r.get("Date")
                    value = r.get("Value")
                    if date is None or value is None:
                        continue
                    # Prefer real smart-meter telemetry but accept anything with a value.
                    if r.get("Type") and SMART_METER_TYPE not in r["Type"]:
                        # keep monthly validated points too, they are still valid indices
                        pass
                    meter = (r.get("Meter") or {}).get("SerialNumber") or r.get("MeterNo")
                    by_date[date] = DailyReading(date=date, value=float(value), meter_serial=meter)

        return [by_date[d] for d in sorted(by_date)]
