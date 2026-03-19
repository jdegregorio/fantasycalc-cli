"""Tests for FantasyCalcClient."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests
import responses

from fantasycalc_cli.client import (
    BASE_URL,
    FantasyCalcCache,
    FantasyCalcClient,
    FantasyCalcRequestError,
)

# ------------------------------------------------------------------
# Sample data
# ------------------------------------------------------------------

SAMPLE_VALUES: list[dict] = [
    {
        "player": {
            "name": "Patrick Mahomes",
            "position": "QB",
            "maybeTeam": "KC",
            "age": 30,
            "fleaflickerId": 14839,
            "sleeperId": "4046",
            "espnId": 3139477,
        },
        "value": 9500,
        "overallRank": 1,
        "positionRank": 1,
    },
    {
        "player": {
            "name": "Ja'Marr Chase",
            "position": "WR",
            "maybeTeam": "CIN",
            "age": 25,
            "fleaflickerId": 16640,
            "sleeperId": "7564",
        },
        "value": 9400,
        "overallRank": 2,
        "positionRank": 1,
    },
    {
        "player": {
            "name": "Bijan Robinson",
            "position": "RB",
            "maybeTeam": "ATL",
            "age": 23,
            "fleaflickerId": 17001,
        },
        "value": 9300,
        "overallRank": 3,
        "positionRank": 1,
    },
    {
        "player": {
            "name": "Sam LaPorta",
            "position": "TE",
            "maybeTeam": "DET",
            "age": 24,
        },
        "value": 7000,
        "overallRank": 15,
        "positionRank": 1,
    },
]


# ------------------------------------------------------------------
# Cache
# ------------------------------------------------------------------


class TestFantasyCalcCache:
    def test_save_and_load(self, tmp_path: Path):
        cache = FantasyCalcCache(tmp_path)
        cache.save(
            is_dynasty=True,
            num_qbs=2,
            num_teams=12,
            ppr=1,
            values=SAMPLE_VALUES,
        )

        loaded = cache.load(
            is_dynasty=True,
            num_qbs=2,
            num_teams=12,
            ppr=1,
            ttl=60,
        )
        assert loaded == SAMPLE_VALUES

    def test_clear(self, tmp_path: Path):
        cache = FantasyCalcCache(tmp_path)
        cache.save(
            is_dynasty=True,
            num_qbs=2,
            num_teams=12,
            ppr=1,
            values=SAMPLE_VALUES,
        )
        removed = cache.clear()
        assert removed == 1
        assert list(tmp_path.glob("*.json")) == []


# ------------------------------------------------------------------
# fetch_values
# ------------------------------------------------------------------


class TestFetchValues:
    @responses.activate
    def test_fetch_values_default_params(self, tmp_path: Path):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json=SAMPLE_VALUES,
            status=200,
        )

        client = FantasyCalcClient(cache=FantasyCalcCache(tmp_path))
        result, source = client.fetch_values()

        assert result == SAMPLE_VALUES
        assert source == "api"
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert "isDynasty=true" in req.url
        assert "numQbs=2" in req.url
        assert "numTeams=12" in req.url
        assert "ppr=1" in req.url

    @responses.activate
    def test_fetch_values_redraft(self, tmp_path: Path):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json=[],
            status=200,
        )

        client = FantasyCalcClient(cache=FantasyCalcCache(tmp_path))
        result, source = client.fetch_values(is_dynasty=False, num_qbs=1, num_teams=10, ppr=0)

        assert result == []
        assert source == "api"
        req = responses.calls[0].request
        assert "isDynasty=false" in req.url
        assert "numQbs=1" in req.url
        assert "numTeams=10" in req.url
        assert "ppr=0" in req.url

    @responses.activate
    def test_fetch_values_uses_cache_when_enabled(self, tmp_path: Path):
        cache = FantasyCalcCache(tmp_path)
        cache.save(
            is_dynasty=True,
            num_qbs=2,
            num_teams=12,
            ppr=1,
            values=SAMPLE_VALUES,
        )

        client = FantasyCalcClient(cache=cache)
        result, source = client.fetch_values()

        assert result == SAMPLE_VALUES
        assert source == "cache"
        assert len(responses.calls) == 0

    @responses.activate
    def test_fetch_values_falls_back_to_stale_cache(self, tmp_path: Path):
        cache = FantasyCalcCache(tmp_path)
        cache_path = cache.save(
            is_dynasty=True,
            num_qbs=2,
            num_teams=12,
            ppr=1,
            values=SAMPLE_VALUES,
        )
        cache_path.touch()

        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            body=requests.ConnectionError("boom"),
        )

        client = FantasyCalcClient(cache=cache, retries=0)
        result, source = client.fetch_values(cache_ttl=0)

        assert result == SAMPLE_VALUES
        assert source == "stale-cache"

    @responses.activate
    def test_fetch_values_http_error(self, tmp_path: Path):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json={"error": "bad request"},
            status=500,
        )

        client = FantasyCalcClient(cache=FantasyCalcCache(tmp_path), retries=0)
        with pytest.raises(FantasyCalcRequestError, match="HTTP 500"):
            client.fetch_values(use_cache=False)

    @responses.activate
    def test_fetch_values_invalid_payload(self, tmp_path: Path):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json={"players": []},
            status=200,
        )

        client = FantasyCalcClient(cache=FantasyCalcCache(tmp_path), retries=0)
        with pytest.raises(FantasyCalcRequestError, match="unexpected response format"):
            client.fetch_values(use_cache=False)


# ------------------------------------------------------------------
# search_player
# ------------------------------------------------------------------


class TestSearchPlayer:
    def test_exact_match(self):
        results = FantasyCalcClient.search_player("Patrick Mahomes", SAMPLE_VALUES)
        assert len(results) == 1
        assert results[0]["player"]["name"] == "Patrick Mahomes"

    def test_partial_match(self):
        results = FantasyCalcClient.search_player("chase", SAMPLE_VALUES)
        assert len(results) == 1
        assert results[0]["player"]["name"] == "Ja'Marr Chase"

    def test_case_insensitive(self):
        results = FantasyCalcClient.search_player("BIJAN", SAMPLE_VALUES)
        assert len(results) == 1

    def test_no_match(self):
        results = FantasyCalcClient.search_player("Nobody Here", SAMPLE_VALUES)
        assert results == []

    def test_multiple_matches(self):
        results = FantasyCalcClient.search_player("a", SAMPLE_VALUES)
        assert len(results) >= 2

    def test_exact_flag(self):
        results = FantasyCalcClient.search_player("patrick mahomes", SAMPLE_VALUES, exact=True)
        assert len(results) == 1
        assert FantasyCalcClient.search_player("patrick", SAMPLE_VALUES, exact=True) == []


# ------------------------------------------------------------------
# build_platform_index
# ------------------------------------------------------------------


class TestBuildPlatformIndex:
    def test_fleaflicker_index(self):
        index = FantasyCalcClient.build_platform_index(SAMPLE_VALUES, "fleaflicker")
        assert "14839" in index
        assert "16640" in index
        assert "17001" in index
        assert len(index) == 3

    def test_sleeper_index(self):
        index = FantasyCalcClient.build_platform_index(SAMPLE_VALUES, "sleeper")
        assert "4046" in index
        assert "7564" in index
        assert len(index) == 2

    def test_espn_index(self):
        index = FantasyCalcClient.build_platform_index(SAMPLE_VALUES, "espn")
        assert "3139477" in index
        assert len(index) == 1

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            FantasyCalcClient.build_platform_index(SAMPLE_VALUES, "nope")

    def test_case_insensitive_platform(self):
        index = FantasyCalcClient.build_platform_index(SAMPLE_VALUES, "Fleaflicker")
        assert len(index) == 3

    def test_empty_values(self):
        index = FantasyCalcClient.build_platform_index([], "fleaflicker")
        assert index == {}
