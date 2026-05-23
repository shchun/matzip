import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock

import matzip_mcp as mcp
from conftest import needs_db


# ── _haversine (순수 단위 테스트) ────────────────────────────────────────────

class TestHaversine:
    def test_same_point_is_zero(self):
        assert mcp._haversine(37.5, 127.0, 37.5, 127.0) == 0.0

    def test_north_south_001deg(self):
        """0.01° 위도 이동 ≈ 1112m"""
        d = mcp._haversine(37.50, 127.0, 37.51, 127.0)
        assert 1100 < d < 1130

    def test_east_west_001deg_at_seoul(self):
        """서울 위도에서 0.01° 경도 이동 ≈ 883m"""
        d = mcp._haversine(37.5, 127.00, 37.5, 127.01)
        assert 870 < d < 900

    def test_symmetry(self):
        d1 = mcp._haversine(37.5, 127.0, 37.51, 127.01)
        d2 = mcp._haversine(37.51, 127.01, 37.5, 127.0)
        assert abs(d1 - d2) < 0.001

    def test_sadang_to_sinchon(self):
        """사당역 → 신촌역 실측 약 9.5km"""
        d = mcp._haversine(37.4768, 126.9816, 37.5549, 126.9368)
        assert 9300 < d < 9800


# ── _db_find_nearby (DB 통합 테스트) ─────────────────────────────────────────

@needs_db
class TestDbFindNearby:
    def test_sadang_500m_finds_multiple(self):
        results = mcp._db_find_nearby(37.4878, 126.9803, 500)
        assert len(results) >= 3

    def test_sadang_contains_expected_restaurant(self):
        results = mcp._db_find_nearby(37.4878, 126.9803, 500)
        names = [r["name"] for r in results]
        assert "시민소머리국밥" in names

    def test_results_sorted_by_distance(self):
        results = mcp._db_find_nearby(37.4878, 126.9803, 500)
        distances = [r["distance_m"] for r in results]
        assert distances == sorted(distances)

    def test_all_within_radius(self):
        results = mcp._db_find_nearby(37.4878, 126.9803, 500)
        for r in results:
            assert r["distance_m"] <= 500

    def test_namsan_no_results(self):
        """남산 정상 — 저장된 맛집 없음"""
        results = mcp._db_find_nearby(37.5512, 126.9882, 300)
        assert len(results) == 0

    def test_result_has_required_keys(self):
        results = mcp._db_find_nearby(37.4878, 126.9803, 500)
        assert len(results) > 0
        required = {"id", "name", "address", "memo", "lat", "lng", "distance_m"}
        for r in results:
            assert required <= r.keys()

    def test_distance_m_is_integer(self):
        results = mcp._db_find_nearby(37.4878, 126.9803, 500)
        for r in results:
            assert isinstance(r["distance_m"], int)


# ── _geocode_area (mock 테스트) ───────────────────────────────────────────────

class TestGeocodeArea:
    def _mock_response(self, lat, lng):
        resp = MagicMock()
        resp.json.return_value = {
            "results": [{"geometry": {"location": {"lat": lat, "lng": lng}}}]
        }
        return resp

    def test_returns_lat_lng_on_success(self):
        with patch("requests.get", return_value=self._mock_response(37.5571, 126.9258)):
            result = mcp._geocode_area("홍대")
        assert result == pytest.approx((37.5571, 126.9258))

    def test_returns_none_on_empty_result(self):
        resp = MagicMock()
        resp.json.return_value = {"results": []}
        with patch("requests.get", return_value=resp):
            result = mcp._geocode_area("존재하지않는지역xyz")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("requests.get", side_effect=Exception("timeout")):
            result = mcp._geocode_area("홍대")
        assert result is None


# ── _get_current_location ─────────────────────────────────────────────────────

class TestGetCurrentLocation:
    def test_uses_home_env_vars_when_set(self, monkeypatch):
        monkeypatch.setenv("HOME_LAT", "37.4878")
        monkeypatch.setenv("HOME_LNG", "126.9803")
        result = mcp._get_current_location()
        assert result == pytest.approx((37.4878, 126.9803))

    def test_falls_back_to_ip_api(self, monkeypatch):
        monkeypatch.delenv("HOME_LAT", raising=False)
        monkeypatch.delenv("HOME_LNG", raising=False)
        resp = MagicMock()
        resp.json.return_value = {"status": "success", "lat": 37.5, "lon": 127.0}
        with patch("requests.get", return_value=resp):
            result = mcp._get_current_location()
        assert result == pytest.approx((37.5, 127.0))

    def test_returns_none_on_ip_api_failure(self, monkeypatch):
        monkeypatch.delenv("HOME_LAT", raising=False)
        monkeypatch.delenv("HOME_LNG", raising=False)
        with patch("requests.get", side_effect=Exception("network error")):
            result = mcp._get_current_location()
        assert result is None


# ── find_nearby tool — 반경 자동 확장 ─────────────────────────────────────────

@needs_db
class TestFindNearbyTool:
    def _run(self, lat, lng, radius=1000):
        return asyncio.run(mcp.call_tool("find_nearby", {"lat": lat, "lng": lng, "radius_m": radius}))

    def test_returns_text_content(self):
        result = self._run(37.4878, 126.9803)
        assert len(result) == 1
        assert result[0].type == "text"

    def test_result_is_valid_json(self):
        result = self._run(37.4878, 126.9803)
        data = json.loads(result[0].text)
        assert "count" in data and "places" in data and "radius_used_m" in data

    def test_auto_expands_radius_when_few_results(self):
        """맛집 없는 곳에서 시작 → 반경 자동 확장"""
        result = self._run(37.5512, 126.9882, radius=100)
        data = json.loads(result[0].text)
        assert data["radius_used_m"] > 100


# ── check_and_notify — notified 집합 관리 ────────────────────────────────────

class TestCheckAndNotify:
    SAMPLE_PLACES = [
        {"id": 1, "name": "시민소머리국밥", "address": "서울 동작구", "memo": "",
         "lat": 37.488, "lng": 126.979, "distance_m": 120},
        {"id": 2, "name": "파이공장", "address": "서울 동작구", "memo": "",
         "lat": 37.487, "lng": 126.979, "distance_m": 135},
    ]

    def setup_method(self):
        mcp._notified.clear()

    def _run(self):
        with patch.object(mcp, "_get_current_location", return_value=(37.4878, 126.9803)), \
             patch.object(mcp, "_db_find_nearby", return_value=self.SAMPLE_PLACES), \
             patch.object(mcp, "_reverse_geocode", return_value="사당동"), \
             patch.object(mcp, "_send_slack_notification") as mock_slack:
            result = asyncio.run(mcp.call_tool("check_and_notify", {}))
            return result, mock_slack

    def test_new_places_trigger_slack(self):
        result, mock_slack = self._run()
        data = json.loads(result[0].text)
        assert data["new_count"] == 2
        mock_slack.assert_called_once()

    def test_already_notified_places_are_skipped(self):
        self._run()  # 첫 번째 호출 → 알림
        result, mock_slack = self._run()  # 두 번째 호출 → 이미 알림
        data = json.loads(result[0].text)
        assert data["new_count"] == 0
        mock_slack.assert_not_called()

    def test_location_failure_returns_error(self):
        with patch.object(mcp, "_get_current_location", return_value=None):
            result = asyncio.run(mcp.call_tool("check_and_notify", {}))
        data = json.loads(result[0].text)
        assert "error" in data


# ── get_area_clusters (DB 통합 테스트) ───────────────────────────────────────

@needs_db
class TestGetAreaClusters:
    def test_returns_up_to_5_clusters(self):
        result = asyncio.run(mcp.call_tool("get_area_clusters", {}))
        clusters = json.loads(result[0].text)
        assert 1 <= len(clusters) <= 5

    def test_clusters_have_required_keys(self):
        result = asyncio.run(mcp.call_tool("get_area_clusters", {}))
        clusters = json.loads(result[0].text)
        for c in clusters:
            assert {"lat", "lng", "count", "area"} <= c.keys()

    def test_clusters_are_non_overlapping(self):
        """각 클러스터 간 거리 > 3km"""
        result = asyncio.run(mcp.call_tool("get_area_clusters", {}))
        clusters = json.loads(result[0].text)
        for i, a in enumerate(clusters):
            for b in clusters[i + 1:]:
                dist = mcp._haversine(a["lat"], a["lng"], b["lat"], b["lng"])
                assert dist > 3000, f"{a['area']}↔{b['area']} 거리 {dist:.0f}m < 3km"
