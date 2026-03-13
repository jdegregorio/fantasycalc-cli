"""Tests for FantasyCalcClient."""

from __future__ import annotations

import pytest
import responses

from fantasycalc_cli.client import BASE_URL, FantasyCalcClient

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
# fetch_values
# ------------------------------------------------------------------


class TestFetchValues:
    @responses.activate
    def test_fetch_values_default_params(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json=SAMPLE_VALUES,
            status=200,
        )

        client = FantasyCalcClient()
        result = client.fetch_values()

        assert result == SAMPLE_VALUES
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert "isDynasty=true" in req.url
        assert "numQbs=2" in req.url
        assert "numTeams=12" in req.url
        assert "ppr=1" in req.url

    @responses.activate
    def test_fetch_values_redraft(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json=[],
            status=200,
        )

        client = FantasyCalcClient()
        result = client.fetch_values(is_dynasty=False, num_qbs=1, num_teams=10, ppr=0)

        assert result == []
        req = responses.calls[0].request
        assert "isDynasty=false" in req.url
        assert "numQbs=1" in req.url
        assert "numTeams=10" in req.url
        assert "ppr=0" in req.url

    @responses.activate
    def test_fetch_values_http_error(self):
        responses.add(
            responses.GET,
            f"{BASE_URL}/values/current",
            json={"error": "bad request"},
            status=500,
        )

        client = FantasyCalcClient()
        with pytest.raises(Exception):
            client.fetch_values()


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
        # Both names contain "a"
        results = FantasyCalcClient.search_player("a", SAMPLE_VALUES)
        assert len(results) >= 2


# ------------------------------------------------------------------
# build_platform_index
# ------------------------------------------------------------------


class TestBuildPlatformIndex:
    def test_fleaflicker_index(self):
        index = FantasyCalcClient.build_platform_index(SAMPLE_VALUES, "fleaflicker")
        assert "14839" in index
        assert "16640" in index
        assert "17001" in index
        # Sam LaPorta has no fleaflickerId
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
