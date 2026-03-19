"""HTTP client for the FantasyCalc API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.fantasycalc.com"
DEFAULT_CACHE_TTL = 300
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "fantasycalc-cli"

# Mapping of platform name to the player-dict key that holds the platform ID.
_PLATFORM_ID_KEYS: dict[str, str] = {
    "fleaflicker": "fleaflickerId",
    "sleeper": "sleeperId",
    "espn": "espnId",
    "yahoo": "yahooId",
    "mfl": "mflId",
}

SUPPORTED_PLATFORMS: list[str] = sorted(_PLATFORM_ID_KEYS)


class FantasyCalcClientError(RuntimeError):
    """Base error for client failures."""


class FantasyCalcRequestError(FantasyCalcClientError):
    """Raised when the upstream API request fails."""


class FantasyCalcCache:
    """Simple JSON file cache for API responses."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = cache_dir

    def cache_path_for(
        self,
        *,
        is_dynasty: bool,
        num_qbs: int,
        num_teams: int,
        ppr: float,
    ) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        slug = (
            f"values-dynasty-{int(is_dynasty)}-qbs-{num_qbs}-teams-{num_teams}"
            f"-ppr-{str(ppr).replace('.', '_')}.json"
        )
        return self.cache_dir / slug

    def load(
        self,
        *,
        is_dynasty: bool,
        num_qbs: int,
        num_teams: int,
        ppr: float,
        ttl: int,
    ) -> list[dict[str, Any]] | None:
        path = self.cache_path_for(
            is_dynasty=is_dynasty,
            num_qbs=num_qbs,
            num_teams=num_teams,
            ppr=ppr,
        )
        if not path.exists():
            return None

        age_seconds = time.time() - path.stat().st_mtime
        if age_seconds > ttl:
            return None

        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

        if isinstance(payload, list):
            return payload
        return None

    def save(
        self,
        *,
        is_dynasty: bool,
        num_qbs: int,
        num_teams: int,
        ppr: float,
        values: list[dict[str, Any]],
    ) -> Path:
        path = self.cache_path_for(
            is_dynasty=is_dynasty,
            num_qbs=num_qbs,
            num_teams=num_teams,
            ppr=ppr,
        )
        path.write_text(json.dumps(values, indent=2))
        return path

    def clear(self) -> int:
        if not self.cache_dir.exists():
            return 0

        removed = 0
        for entry in self.cache_dir.glob("*.json"):
            entry.unlink(missing_ok=True)
            removed += 1
        return removed


class FantasyCalcClient:
    """Thin wrapper around the FantasyCalc public API."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = 30,
        retries: int = 2,
        cache: FantasyCalcCache | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.cache = cache or FantasyCalcCache()

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def fetch_values(
        self,
        *,
        is_dynasty: bool = True,
        num_qbs: int = 2,
        num_teams: int = 12,
        ppr: float = 1,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        use_cache: bool = True,
        refresh_cache: bool = False,
    ) -> tuple[list[dict], str]:
        """Fetch current player market values.

        Parameters
        ----------
        is_dynasty : bool
            ``True`` for dynasty, ``False`` for redraft.
        num_qbs : int
            Number of starting QBs (2 = superflex).
        num_teams : int
            League size.
        ppr : float
            Points-per-reception scoring (0, 0.5, or 1).
        cache_ttl : int
            Maximum age in seconds for cached results.
        use_cache : bool
            Whether to read/write local cache files.
        refresh_cache : bool
            Skip cache reads and force a fresh API request.

        Returns
        -------
        tuple[list[dict], str]
            Raw value rows from the API and the data source label.
        """
        if use_cache and not refresh_cache:
            cached = self.cache.load(
                is_dynasty=is_dynasty,
                num_qbs=num_qbs,
                num_teams=num_teams,
                ppr=ppr,
                ttl=cache_ttl,
            )
            if cached is not None:
                return cached, "cache"

        url = f"{self.base_url}/values/current"
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 2):
            try:
                response = requests.get(
                    url,
                    params={
                        "isDynasty": str(is_dynasty).lower(),
                        "numQbs": num_qbs,
                        "numTeams": num_teams,
                        "ppr": ppr,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise FantasyCalcRequestError(
                        "FantasyCalc API returned an unexpected response format."
                    )
                if use_cache:
                    self.cache.save(
                        is_dynasty=is_dynasty,
                        num_qbs=num_qbs,
                        num_teams=num_teams,
                        ppr=ppr,
                        values=payload,
                    )
                return payload, "api"
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt > self.retries:
                    break
                time.sleep(min(attempt * 0.5, 2))

        if use_cache:
            stale = self.cache.load(
                is_dynasty=is_dynasty,
                num_qbs=num_qbs,
                num_teams=num_teams,
                ppr=ppr,
                ttl=10**9,
            )
            if stale is not None:
                return stale, "stale-cache"

        assert last_error is not None
        raise FantasyCalcRequestError(self._format_request_error(last_error)) from last_error

    @staticmethod
    def _format_request_error(exc: Exception) -> str:
        if isinstance(exc, requests.Timeout):
            return "FantasyCalc API request timed out. Try again or use cached data."
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return (
                "FantasyCalc API returned "
                f"HTTP {exc.response.status_code}. Try again shortly."
            )
        if isinstance(exc, requests.ConnectionError):
            return "Could not connect to FantasyCalc API. Check your network or use cached data."
        return f"FantasyCalc API request failed: {exc}"

    # ------------------------------------------------------------------
    # Local helpers (operate on already-fetched data)
    # ------------------------------------------------------------------

    @staticmethod
    def search_player(name: str, values: list[dict], *, exact: bool = False) -> list[dict]:
        """Return rows whose player name matches *name* case-insensitively."""
        needle = name.casefold().strip()
        results: list[dict] = []
        for row in values:
            player = row.get("player") or {}
            player_name = str(player.get("name", "")).strip()
            candidate = player_name.casefold()
            matched = candidate == needle if exact else needle in candidate
            if matched:
                results.append(row)
        return results

    @staticmethod
    def build_platform_index(
        values: list[dict],
        platform: str = "fleaflicker",
    ) -> dict[str, dict]:
        """Build {platform_id: row} lookup from a list of value rows."""
        key = _PLATFORM_ID_KEYS.get(platform.lower())
        if key is None:
            supported = ", ".join(sorted(_PLATFORM_ID_KEYS))
            raise ValueError(
                f"Unknown platform {platform!r}. Supported platforms: {supported}"
            )

        index: dict[str, dict] = {}
        for row in values:
            player = row.get("player") or {}
            platform_id = player.get(key)
            if platform_id is not None:
                index[str(platform_id)] = row
        return index
