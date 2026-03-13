"""HTTP client for the FantasyCalc API."""

from __future__ import annotations

import requests

BASE_URL = "https://api.fantasycalc.com"

# Mapping of platform name to the player-dict key that holds the platform ID.
_PLATFORM_ID_KEYS: dict[str, str] = {
    "fleaflicker": "fleaflickerId",
    "sleeper": "sleeperId",
    "espn": "espnId",
    "yahoo": "yahooId",
    "mfl": "mflId",
}


class FantasyCalcClient:
    """Thin wrapper around the FantasyCalc public API."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def fetch_values(
        self,
        *,
        is_dynasty: bool = True,
        num_qbs: int = 2,
        num_teams: int = 12,
        ppr: int = 1,
    ) -> list[dict]:
        """Fetch current player market values.

        Parameters
        ----------
        is_dynasty : bool
            ``True`` for dynasty, ``False`` for redraft.
        num_qbs : int
            Number of starting QBs (2 = superflex).
        num_teams : int
            League size.
        ppr : int
            Points-per-reception scoring (0, 0.5, or 1).

        Returns
        -------
        list[dict]
            Raw value rows from the API.
        """
        url = f"{self.base_url}/values/current"
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
        return response.json()

    # ------------------------------------------------------------------
    # Local helpers (operate on already-fetched data)
    # ------------------------------------------------------------------

    @staticmethod
    def search_player(name: str, values: list[dict]) -> list[dict]:
        """Return rows whose player name contains *name* (case-insensitive)."""
        needle = name.lower()
        results: list[dict] = []
        for row in values:
            player = row.get("player") or {}
            player_name = player.get("name", "")
            if needle in player_name.lower():
                results.append(row)
        return results

    @staticmethod
    def build_platform_index(
        values: list[dict],
        platform: str = "fleaflicker",
    ) -> dict[str, dict]:
        """Build {platform_id: row} lookup from a list of value rows.

        Parameters
        ----------
        values : list[dict]
            Rows returned by :meth:`fetch_values`.
        platform : str
            One of ``fleaflicker``, ``sleeper``, ``espn``, ``yahoo``, ``mfl``.

        Returns
        -------
        dict[str, dict]
            Mapping of string platform ID to the full value row.

        Raises
        ------
        ValueError
            If *platform* is not recognised.
        """
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
