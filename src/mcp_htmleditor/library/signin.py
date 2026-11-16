"""Google sign in, login attempts and sessions of the web library mode (SPEC-0025, DEC-012 to DEC-017).

The OpenID Connect code flow with PKCE: ``Accounts.begin_login`` stores an attempt (hashed ``state``, ``nonce``,
verifier, destination, hashed browser id) and returns Google's address; ``Accounts.finish_login`` deletes the attempt
first (single use), checks its age and browser, exchanges the code at ``token_uri`` and validates the ID token claims
(decoded, not signature checked: it comes straight from Google over TLS), then stores a session row keyed by the
SHA-256 of a 256 bit token. Every failure is one ``SignInUnavailable`` whose text is a fixed reason, never a value.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import logging
import re
import secrets
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlencode, urlsplit

from ..tracing import trace_span
from .store import Database

logger = logging.getLogger(__name__)

SESSION_COOKIE: Final = "lib"
BROWSER_COOKIE: Final = "lib-b"
SESSION_SECONDS: Final = 2_592_000  # 30 days exactly, never extended (DEC-017)
LOGIN_SECONDS: Final = 600
TOKEN_TIMEOUT_SECONDS: Final = 10.0
MAX_TOKEN_ANSWER_BYTES: Final = 1_048_576
GOOGLE_ISSUERS: Final = frozenset({"accounts.google.com", "https://accounts.google.com"})
SAFE_DESTINATION: Final = re.compile(r"^/[A-Za-z0-9._~/%-]*$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: the client secret is posted to ``token_uri`` and to nothing it points at."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


# No proxy (an environment proxy would see the secret) and no redirect.
_DIRECT_OPENER: Final = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

_CREDENTIAL_KEYS: Final = ("client_id", "client_secret", "auth_uri", "token_uri")
_URL_SCHEMES: Final = frozenset({"http", "https"})


class SignInUnavailable(Exception):  # noqa: N818 - the name of the user text, "Sign-in is unavailable"
    """The sign in cannot complete; the message is a fixed reason for the log, never an address or a token."""


@dataclass(frozen=True, slots=True)
class GoogleCredentials:
    """The ``web`` block of the operator's client file."""

    client_id: str
    client_secret: str
    auth_uri: str
    token_uri: str
    redirect_uris: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Session:
    """A live session: the person's lower case address and the hash of the cookie token."""

    email: str
    token_hash: str
    created_at: float
    expires_at: float


@dataclass(frozen=True, slots=True)
class NewSession:
    """What ``finish_login`` returns: the raw token (only here), its session and the stored destination."""

    token: str
    session: Session
    destination: str


class GoogleClient:
    """The two calls to Google: the authorization address and the code exchange (DEC-012, DEC-015)."""

    def __init__(
        self, credentials_file: Path | None, redirect_uri: str, timeout: float = TOKEN_TIMEOUT_SECONDS
    ) -> None:
        self.redirect_uri = redirect_uri
        self.timeout = timeout
        self._credentials = read_credentials(credentials_file)
        if self._credentials is not None and redirect_uri not in self._credentials.redirect_uris:
            logger.warning(
                "The sign in return address %s is not listed in redirect_uris of the Google credentials file:"
                " add it in the Google console or every sign in fails",
                redirect_uri,
            )

    @property
    def client_id(self) -> str:
        return self._configured().client_id

    def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        """Google's address for this attempt; ``prompt=select_account`` always shows the account chooser."""
        credentials = self._configured()
        query = {
            "response_type": "code",
            "client_id": credentials.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{credentials.auth_uri}?{urlencode(query)}"

    def exchange(self, code: str, verifier: str) -> dict[str, Any]:
        """POST the code to ``token_uri`` and return the decoded ID token claims; any failure is SignInUnavailable."""
        credentials = self._configured()
        form = urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
            }
        ).encode()
        request = urllib.request.Request(  # noqa: S310 - the scheme is checked to be http(s) when the file is read
            credentials.token_uri,
            data=form,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        with trace_span("auth.google_token") as span:
            try:
                with _DIRECT_OPENER.open(request, timeout=self.timeout) as response:  # nosec B310
                    span.set_attribute("http.status_code", response.status)
                    if response.status != HTTPStatus.OK:
                        raise SignInUnavailable(f"token endpoint answered {response.status}")
                    answer = response.read(MAX_TOKEN_ANSWER_BYTES + 1)
            except urllib.error.HTTPError as exc:
                span.set_attribute("http.status_code", exc.code)
                raise SignInUnavailable(f"token endpoint answered {exc.code}") from None
            except (OSError, http.client.HTTPException) as exc:
                raise SignInUnavailable(f"token endpoint unreachable ({type(exc).__name__})") from None
        if len(answer) > MAX_TOKEN_ANSWER_BYTES:
            raise SignInUnavailable("token answer too large")
        return _id_token_claims(answer)

    def _configured(self) -> GoogleCredentials:
        if self._credentials is None:
            raise SignInUnavailable("no usable Google credentials file")
        return self._credentials


class Accounts:
    """Login attempts and sessions in the library database; ``clock`` is injected (DEC-032)."""

    def __init__(self, database: Database, google: GoogleClient, clock: Callable[[], float]) -> None:
        self._database = database
        self._google = google
        self._clock = clock

    def begin_login(self, browser_id: str | None, destination: str) -> tuple[str, str]:
        """Store an attempt and return ``(Google's address, browser id)``; a new browser id when ``None``."""
        browser = browser_id or secrets.token_urlsafe(16)
        state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        url = self._google.authorization_url(state, nonce, challenge)  # raises before anything is stored
        now = self._clock()
        with self._database.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM logins WHERE created_at <= ?", (now - LOGIN_SECONDS,))
            connection.execute(
                "INSERT INTO logins(state_hash, nonce, verifier, destination, browser_hash, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (token_hash(state), nonce, verifier, safe_destination(destination), token_hash(browser), now),
            )
        return url, browser

    def finish_login(self, state: str, code: str, browser_id: str | None) -> NewSession:
        """The attempt of ``state`` is deleted first, then checked, then the code exchanged and a session stored."""
        with self._database.transaction(immediate=True) as connection:
            rows = connection.execute(
                "DELETE FROM logins WHERE state_hash = ? RETURNING nonce, verifier, destination, browser_hash,"
                " created_at",
                (token_hash(state),),
            ).fetchall()
        if not rows:
            raise SignInUnavailable("unknown or already used sign in answer")
        nonce, verifier, destination, browser_hash, created_at = rows[0]
        if not 0 <= self._clock() - created_at < LOGIN_SECONDS:
            raise SignInUnavailable("sign in attempt expired")
        if browser_id is None or not secrets.compare_digest(token_hash(browser_id), browser_hash):
            raise SignInUnavailable("sign in answer from another browser")
        claims = self._google.exchange(code, verifier)
        email = validate_claims(claims, self._google.client_id, nonce, self._clock())
        return NewSession(*self._create_session(email), destination=destination)

    def session_for(self, token: str | None) -> Session | None:
        """The live session of a cookie token (``now < expires_at``), else None."""
        if not token:
            return None
        row = (
            self._database.connection()
            .execute(
                "SELECT email, id_hash, created_at, expires_at FROM sessions WHERE id_hash = ? AND expires_at > ?",
                (token_hash(token), self._clock()),
            )
            .fetchone()
        )
        return Session(*row) if row is not None else None

    def end_session(self, token: str) -> None:
        """Sign out: the row is deleted, so a copy of the cookie resolves to nothing (DEC-017)."""
        with self._database.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM sessions WHERE id_hash = ?", (token_hash(token),))

    def _create_session(self, email: str) -> tuple[str, Session]:
        token = secrets.token_urlsafe(32)
        now = self._clock()
        session = Session(email, token_hash(token), now, now + SESSION_SECONDS)
        with trace_span("session.create"), self._database.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO sessions(id_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (session.token_hash, email, session.created_at, session.expires_at),
            )
        return token, session


def read_credentials(path: Path | None) -> GoogleCredentials | None:
    """The ``web`` block of the operator's file, or None after one error line (the server still starts)."""
    if path is None:
        logger.error("No Google credentials file (HTMLEDITOR_GOOGLE_CREDENTIALS_FILE): every sign in will fail")
        return None
    try:
        web = json.loads(path.read_text(encoding="utf-8"))["web"]
        values = {key: web[key] for key in _CREDENTIAL_KEYS}
        redirect_uris = tuple(web.get("redirect_uris", ()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.error("Google credentials file %s unreadable (%s): every sign in will fail", path, type(exc).__name__)
        return None
    if not all(isinstance(value, str) and value for value in values.values()) or not all(
        isinstance(uri, str) for uri in redirect_uris
    ):
        logger.error("Google credentials file %s lacks a field of its web block: every sign in will fail", path)
        return None
    if not {urlsplit(values["auth_uri"]).scheme, urlsplit(values["token_uri"]).scheme} <= _URL_SCHEMES:
        logger.error("Google credentials file %s: auth_uri and token_uri must be http(s) addresses", path)
        return None
    return GoogleCredentials(**values, redirect_uris=redirect_uris)


def validate_claims(claims: dict[str, Any], client_id: str, nonce: str, now: float) -> str:
    """The lower case address when every claim holds (DEC-012), else SignInUnavailable naming the claim."""
    expires = claims.get("exp")
    checks = (
        ("iss", claims.get("iss") in GOOGLE_ISSUERS),
        ("aud", claims.get("aud") == client_id),
        ("exp", isinstance(expires, int | float) and not isinstance(expires, bool) and expires > now),
        ("nonce", claims.get("nonce") == nonce),
        ("email_verified", claims.get("email_verified") is True or claims.get("email_verified") == "true"),
        ("email", isinstance(claims.get("email"), str) and bool(claims.get("email"))),
    )
    for name, holds in checks:
        if not holds:
            raise SignInUnavailable("unverified address" if name == "email_verified" else f"invalid claim {name}")
    return str(claims["email"]).lower()


def safe_destination(raw: str | None) -> str:
    """The post sign in address when it is a plain local path (DEC-014), else ``/``.

    The pattern already excludes ``\\``, ``:`` and control characters; ``//`` is refused because a browser reads it as
    another host.
    """
    if raw is None or not SAFE_DESTINATION.fullmatch(raw) or raw.startswith(("//", "/\\")):
        return "/"
    return raw


def token_hash(token: str) -> str:
    """What the tables keep instead of a token, a state or a browser id."""
    return hashlib.sha256(token.encode()).hexdigest()


def _id_token_claims(answer: bytes) -> dict[str, Any]:
    """The payload of ``id_token`` in the token answer (``header.payload.signature``, base64url)."""
    try:
        id_token = json.loads(answer)["id_token"]
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        raise SignInUnavailable("token answer is not a JSON object with an ID token") from None
    if not isinstance(claims, dict):
        raise SignInUnavailable("ID token payload is not an object")
    return claims
