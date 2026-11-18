"""Login against the ASP.NET WebForms portal to obtain the webapi token.

Flow (reverse-engineered):
  1. GET login.aspx  -> sets ASP.NET_SessionId + __AntiXsrfToken cookies and
     returns the hidden WebForms fields (__VIEWSTATE, __VIEWSTATEGENERATOR,
     __AntiXsrfToken) that must be echoed back.
  2. POST login.aspx with those fields + username/password (+ ReturnUrl, spidId).
  3. On success the portal sets a `sol-<sessionid>-at` cookie: that GUID is the
     token used in the /webapi/api/v1/... URLs. `-cs` carries the internal id.

The token rotates on every login, which is why it "expires"; re-running the
login yields a fresh one.
"""
from __future__ import annotations

import logging
import re

from aiohttp import ClientError, ClientSession

from .api import TIMEOUT, AcquaveneteApiError, AcquaveneteAuthError
from .const import HOME_URL, LOGIN_URL

_LOGGER = logging.getLogger(__name__)

_HIDDEN_RE = (
    r'id="{name}"[^>]*?value="([^"]*)"',
    r'name="{name}"[^>]*?value="([^"]*)"',
)


def _hidden(html: str, name: str) -> str:
    for pattern in _HIDDEN_RE:
        m = re.search(pattern.format(name=re.escape(name)), html, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


class AcquaveneteAuth:
    """Performs the portal login and extracts the webapi token."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password

    async def async_login(self) -> tuple[str, str | None]:
        """Return (token, internal_id). Raises AcquaveneteAuthError on failure."""
        try:
            async with self._session.get(LOGIN_URL, timeout=TIMEOUT) as resp:
                html = await resp.text()
        except (ClientError, TimeoutError) as err:
            raise AcquaveneteApiError(f"GET login failed: {err!r}") from err

        viewstate = _hidden(html, "__VIEWSTATE")
        generator = _hidden(html, "__VIEWSTATEGENERATOR")
        xsrf = _hidden(html, "__AntiXsrfToken")
        if not viewstate:
            raise AcquaveneteApiError("Could not read WebForms fields from login page")

        payload = {
            "__AntiXsrfToken": xsrf,
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": generator,
            "ReturnUrl": "/",
            "username": self._username,
            "password": self._password,
            "spidId": "",
        }
        try:
            async with self._session.post(LOGIN_URL, data=payload, timeout=TIMEOUT) as resp:
                await resp.read()
            # Touch the home page so the app finalises its session cookies.
            async with self._session.get(HOME_URL, timeout=TIMEOUT) as resp:
                await resp.read()
        except (ClientError, TimeoutError) as err:
            raise AcquaveneteApiError(f"POST login failed: {err!r}") from err

        token, internal_id = self._extract_from_cookies()
        if not token:
            # Wrong credentials leave us without the -at cookie.
            raise AcquaveneteAuthError("Login did not yield a token (bad credentials?)")
        return token, internal_id

    def _extract_from_cookies(self) -> tuple[str | None, str | None]:
        """Read the `sol-<sessionid>-at` (token) and `-cs` (internal id) cookies."""
        token: str | None = None
        internal_id: str | None = None
        for cookie in self._session.cookie_jar:
            key = cookie.key
            if key.endswith("-at"):
                token = cookie.value
            elif key.endswith("-cs"):
                internal_id = cookie.value
        return token, internal_id
