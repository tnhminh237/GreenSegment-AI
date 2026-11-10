"""Both search entry points use the same query engine and real EDGAR rows."""
import csv
import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import advisor_service as advisor, data_service as data, market_service as market
from api.main import app
import test_market_explorer as fixtures


class MarketSearchModesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        with data.CITY_PATH.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_manual_search_export_never_initialize_gemini(self):
        with patch.object(advisor, "_advisor", side_effect=AssertionError("Gemini unavailable")):
            query = {"sector": "industry", "countries": ["Japan"], "min_sector_share_percent": 30,
                     "cluster_id": 0, "limit": 5}
            response = self.client.post("/api/market/search", json=query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["matching_summary"]["city_count"], 9)
            self.assertEqual(self.client.post("/api/market/export", json={"query": query}).status_code, 200)

    def test_same_ai_and_manual_conditions_produce_identical_results(self):
        for sector in [*data.SECTORS, "all"]:
            query = market.MarketQuery(sector=sector, countries=["Japan"], cluster_id=0,
                                       sort_by="total_ghg", limit=5).model_dump()
            parsed = {"query": query, "interpretation": "Sàng lọc theo dữ liệu.",
                      "assumptions": [], "unsupported_criteria": []}
            with self.subTest(sector=sector), patch.object(advisor._advisor(), "call_gemini", return_value=parsed):
                ai = self.client.post("/api/market/parse", json={"text": "Tìm 5 đô thị Nhật Bản thuộc cụm 0"})
                self.assertEqual(ai.status_code, 200)
                self.assertEqual(ai.json()["unsupported_criteria"], [])
                self.assertEqual(self.client.post("/api/market/search", json=ai.json()["query"]).json(),
                                 self.client.post("/api/market/search", json=query).json())

    def test_sector_cluster_threshold_sort_and_top_n_match_raw_rows(self):
        for sector in [*data.SECTORS, "all"]:
            for cid in [None, 0, 1, 2]:
                sorts = ["total_ghg"] if sector == "all" else ["sector_share", "sector_emissions", "total_ghg"]
                for index, sort_by in enumerate(sorts):
                    limit = [5, 10, 20, 50][(index + (cid or 0)) % 4]
                    threshold = None if sector == "all" else 30
                    query = market.MarketQuery(sector=sector, countries=["Japan", "Vietnam"], cluster_id=cid,
                                               min_sector_share_percent=threshold, sort_by=sort_by, limit=limit)
                    expected = [r for r in self.rows if r["country_name"] in query.countries
                                and (cid is None or int(r["cluster_id"]) == cid)
                                and (threshold is None or float(r[f"share_{sector}_2024"]) * 100 >= threshold)]
                    field = "ghg_total_2024" if sort_by == "total_ghg" else f"{'share' if sort_by == 'sector_share' else 'ghg'}_{sector}_2024"
                    expected.sort(key=lambda r: (-float(r[field]), r["city_id"]))
                    with self.subTest(sector=sector, cluster=cid, sort=sort_by, limit=limit):
                        result = market.search(query)
                        self.assertEqual(result["matching_summary"]["city_count"], len(expected))
                        self.assertEqual([r["city_id"] for r in result["items"]], [r["city_id"] for r in expected[:limit]])

    def test_all_sectors_null_metrics_csv_and_report(self):
        query = market.MarketQuery(sector="all", countries=["Japan"], sort_by="total_ghg", limit=5)
        response = self.client.post("/api/market/search", json=query.model_dump())
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIsNone(result["matching_summary"]["mean_sector_share_percent"])
        self.assertTrue(all(r["sector_share_percent"] is None and r["sector_emissions"] is None for r in result["items"]))
        exported = market.export_csv(market.ExportRequest(query=query))
        rows = list(csv.DictReader(io.StringIO(exported["csv"].lstrip("\ufeff"))))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r["sector_share_percent"] == "" and r["sector_emissions_original_edgar_unit"] == "" for r in rows))
        request = market.ReportRequest(query=query)
        context = market.report_context(request)
        self.assertNotIn("matching.mean_sector_share_percent", context["verified_facts"])
        self.assertFalse(any("share_gap" in key for key in context["verified_facts"]))
        with patch.object(advisor._advisor(), "call_gemini", return_value=fixtures.MarketExplorerTests.report_fixture(context)):
            self.assertEqual(self.client.post("/api/market/report", json=request.model_dump()).status_code, 200)

    def test_all_sectors_rejects_dependent_filters_instead_of_ignoring_them(self):
        for overrides in [{"sort_by": "sector_share"}, {"sort_by": "sector_emissions"},
                          {"min_sector_share_percent": 0}, {"max_sector_share_percent": 90}]:
            with self.subTest(overrides=overrides):
                response = self.client.post("/api/market/search", json={"sector": "all", "sort_by": "total_ghg", **overrides})
                self.assertEqual(response.status_code, 422)

    def test_unsupported_ai_criteria_are_returned_for_revision(self):
        answer = {"query": market.MarketQuery(sector="industry").model_dump(),
                  "interpretation": "Công nghiệp", "assumptions": [],
                  "unsupported_criteria": ["Chưa có dữ liệu ngân sách mua sắm."]}
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer), \
                patch.object(market, "search", side_effect=AssertionError("Parser must not search")):
            response = self.client.post("/api/market/parse", json={"text": "Tìm đô thị có ngân sách mua sắm lớn"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["unsupported_criteria"], answer["unsupported_criteria"])

    def test_parser_cannot_silently_drop_explicit_share_threshold(self):
        answer = {"query": market.MarketQuery(sector="industry").model_dump(),
                  "interpretation": "Công nghiệp", "assumptions": [], "unsupported_criteria": []}
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer):
            response = self.client.post("/api/market/parse", json={"text": "Tìm đô thị có tỷ trọng công nghiệp từ 30%"})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["unsupported_criteria"])

    def test_city_level_search_is_supported_despite_false_model_rejection(self):
        query = market.MarketQuery(sector="industry", countries=["Japan"], min_sector_share_percent=30).model_dump()
        answer = {"query": query, "interpretation": "Đô thị Nhật Bản, Công nghiệp từ 30%.",
                  "assumptions": [], "unsupported_criteria": ["Yêu cầu tìm kiếm theo cấp độ đô thị không được hỗ trợ."]}
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer) as call:
            parsed = self.client.post("/api/market/parse", json={"text": "Tìm đô thị Nhật Bản có tỷ trọng công nghiệp từ 30%"})
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.json()["unsupported_criteria"], [])
        self.assertEqual(parsed.json()["query"], query)
        self.assertTrue(call.call_args.args[0]["dataset_scope"]["city_level_search_supported"])
        self.assertIn("CHUYÊN tìm kiếm ĐÔ THỊ", call.call_args.kwargs["system_rules"])
        result = self.client.post("/api/market/search", json=parsed.json()["query"])
        self.assertEqual(result.json()["matching_summary"]["city_count"], 40)

    def test_city_scope_correction_preserves_genuine_unsupported_conditions(self):
        for criteria, expected in [
            (["Yêu cầu tìm kiếm theo cấp độ đô thị không được hỗ trợ.", "Chưa có dữ liệu ngân sách."], ["Chưa có dữ liệu ngân sách."]),
            (["Yêu cầu tìm kiếm theo cấp độ đô thị không được hỗ trợ, ngân sách chưa có."], ["Yêu cầu tìm kiếm theo cấp độ đô thị không được hỗ trợ, ngân sách chưa có."]),
            (["Không hỗ trợ lọc tên đô thị Hà Nội."], ["Không hỗ trợ lọc tên đô thị Hà Nội."]),
        ]:
            answer = {"query": market.MarketQuery(sector="industry").model_dump(),
                      "interpretation": "Công nghiệp", "assumptions": [], "unsupported_criteria": criteria}
            with self.subTest(criteria=criteria), patch.object(advisor._advisor(), "call_gemini", return_value=answer):
                response = self.client.post("/api/market/parse", json={"text": "Tìm đô thị có ngân sách mua sắm lớn"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["unsupported_criteria"], expected)


if __name__ == "__main__":
    unittest.main()
