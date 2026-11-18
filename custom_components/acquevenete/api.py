"""Client for the (undocumented) Acquevenete self-service API.

The week-consumption-chart endpoint nests one "SMART METERING" reading per day
inside weekly buckets; those daily points give ~daily / 1 m3 resolution.

The webapi token lives in the URL path and rotates on every portal login, so the
client is auth-aware: when a request looks unauthenticated (non-200, an HTML
login redirect, or empty data), it re-logs in once and retries.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import BASE_URL, REQUEST_TIMEOUT, SMART_METER_TYPE

if TYPE_CHECKING:
    from .auth import AcquaveneteAuth

_LOGGER = logging.getLogger(__name__)

TIMEOUT = ClientTimeout(total=REQUEST_TIMEOUT)


def redact(text: str, secret: str | None) -> str:
    """Hide the session token, which lives in the URL path, from messages/logs."""
    return text.replace(secret, "***") if secret else text


class AcquaveneteAuthError(Exception):
    """Raised when credentials/token look invalid or expired."""


class AcquaveneteApiError(Exception):
    """Raised on any other API/transport failure."""


@dataclass
class DailyReading:
    """A single daily meter reading (cumulative index in m3)."""

    date: str
    value: float
    meter_serial: str | None = None


class AcquaveneteClient:
    """Thin async wrapper over the endpoints we need, with auto re-login."""

    def __init__(
        self,
        session: ClientSession,
        auth: "AcquaveneteAuth",
        supply_no: str,
        page: str = "1",
        token: str | None = None,
    ) -> None:
        self._session = session
        self._auth = auth
        self._supply_no = supply_no.strip()
        self._page = str(page).strip() or "1"
        self._token = token

    async def _ensure_token(self) -> str:
        if not self._token:
            self._token, _ = await self._auth.async_login()
        return self._token

    async def _get_json(self, path_template: str):
        """GET a webapi path; re-login once if the token looks expired."""
        token = await self._ensure_token()
        data = await self._try(path_template, token)
        if data is not None:
            return data
        # Token likely expired -> refresh once and retry.
        self._token, _ = await self._auth.async_login()
        data = await self._try(path_template, self._token)
        if data is None:
            raise AcquaveneteAuthError("Still unauthorised after re-login")
        return data

    async def _try(self, path_template: str, token: str):
        """Return parsed JSON, or None if the response looks unauthenticated."""
        url = f"{BASE_URL}/{path_template.format(token=token)}"
        try:
            async with self._session.get(url, timeout=TIMEOUT) as resp:
                if resp.status in (401, 403):
                    return None
                if resp.status != 200:
                    raise AcquaveneteApiError(
                        f"HTTP {resp.status} for {redact(url, token)}"
                    )
                ctype = resp.headers.get("Content-Type", "")
                if "json" not in ctype:
                    # Portal served an HTML login page instead of JSON.
                    return None
                return await resp.json(content_type=None)
        except TimeoutError as err:
            raise AcquaveneteApiError(
                f"Timeout after {REQUEST_TIMEOUT}s for {redact(url, token)}"
            ) from err
        except ClientError as err:
            raise AcquaveneteApiError(redact(str(err), token)) from err

    async def async_validate(self) -> bool:
        """Cheap call used by the config flow to check credentials + supply."""
        data = await self.async_get_daily_readings()
        return len(data) > 0

    async def async_get_daily_readings(self) -> list[DailyReading]:
        """Fetch the week-chart and flatten it to a sorted list of daily readings."""
        payload = await self._get_json(
            "supply-week-consumption-chart/{token}/" + f"{self._supply_no}/{self._page}/"
        )
        return self._flatten(payload)

    @staticmethod
    def _flatten(payload) -> list[DailyReading]:
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
                    meter = (r.get("Meter") or {}).get("SerialNumber") or r.get("MeterNo")
                    by_date[date] = DailyReading(
                        date=date, value=float(value), meter_serial=meter
                    )

        return [by_date[d] for d in sorted(by_date)]
