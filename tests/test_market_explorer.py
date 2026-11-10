"""Offline regression checks against all real EDGAR city rows; Gemini is always mocked."""
import csv
import io
import json
import statistics
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import advisor_service as advisor, data_service as data, market_service as market
from api.main import app


class MarketExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        with data.CITY_PATH.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))
        cls.query = market.MarketQuery(sector="industry", countries=["Japan"], min_sector_share_percent=30)

    @staticmethod
    def report_fixture(context):
        count = context["matching_summary"]["city_count"]
        top = context["top_summary"]["city_count"]
        return {
            "research_request": f"Phạm vi nghiên cứu hiện có {count} đô thị đáp ứng các tiêu chí đã được xác nhận. Danh sách đang hiển thị gồm {top} đô thị theo thứ tự của bộ lọc. Đây là bước sàng lọc bằng dữ liệu phát thải để xác định đối tượng cần tìm hiểu thêm, không phải danh sách doanh nghiệp hoặc khách hàng có nhu cầu mua công nghệ.",
            "emissions_profile": "Tỷ trọng lĩnh vực được nghiên cứu mô tả vị trí tương đối của lĩnh vực trong cơ cấu phát thải đô thị. Lượng phát thải tuyệt đối bổ sung góc nhìn về quy mô theo đơn vị gốc. Hai cách đọc cần được phân biệt; không thể từ một tỷ trọng cao suy ra loại thiết bị, hạ tầng hoặc quy trình đang vận hành tại địa phương.",
            "cluster_distribution": "Phân bố theo các cụm cho thấy các đô thị phù hợp có thể thuộc những cấu trúc phát thải khác nhau. Nhãn cụm mô tả cơ cấu chung, không chứng minh sự đồng nhất về hoạt động sản xuất hoặc điều kiện tiếp cận thị trường.",
            "city_comparisons": [{"city_id": context["representative_cities"][0]["city_id"], "text": "Đô thị này nằm trong phần danh sách được Python lựa chọn để minh họa. Vị trí trong thứ tự phản ánh tiêu chí phát thải được xác nhận, không thể hiện mức sẵn sàng mua sắm. Cần đối chiếu hồ sơ đô thị và điều tra thực tế trước khi xác định đối tượng tiếp cận."}],
            "preliminary_technology_link": "Liên hệ giữa lĩnh vực phát thải và công nghệ chỉ nên xem là một giả thuyết nghiên cứu sơ bộ. Phải xác minh nguồn phát thải và cơ sở vận hành cụ thể; chưa có cơ sở khẳng định một công nghệ nhất định phù hợp hoặc có khách hàng sẵn sàng chi trả.",
            "additional_information": ["Cần bổ sung loại hạ tầng và ngành hoạt động thực tế của các cơ sở liên quan.", "Cần xác minh chính sách áp dụng, ngân sách và đơn vị có quyền quyết định mua sắm.", "Cần khảo sát nhu cầu thực tế, dữ liệu vận hành và điều kiện tiếp cận các bên liên quan."],
            "limitations": "Dữ liệu năm 2024 và K=3 chỉ mô tả phát thải, không dự báo doanh số hoặc nhu cầu thương mại. Đơn vị gốc EDGAR chưa được xác minh nên không chuyển đổi sang đơn vị khác. Các kết luận cần được kiểm chứng bằng nguồn thông tin bổ sung."}

    def expected(self, query):
        rows = [r for r in self.rows if (not query.countries or r["country_name"] in query.countries)
                and (query.cluster_id is None or int(r["cluster_id"]) == query.cluster_id)
                and (query.min_sector_share_percent is None or float(r[f"share_{query.sector}_2024"]) * 100 >= query.min_sector_share_percent)
                and (query.max_sector_share_percent is None or float(r[f"share_{query.sector}_2024"]) * 100 <= query.max_sector_share_percent)]
        field = {"sector_share": f"share_{query.sector}_2024", "sector_emissions": f"ghg_{query.sector}_2024", "total_ghg": "ghg_total_2024"}[query.sort_by]
        return sorted(rows, key=lambda r: ((-1 if query.sort_order == "desc" else 1) * float(r[field]), r["city_id"]))

    def test_japan_industry_example_is_not_a_dominant_sector_filter(self):
        response = self.client.post("/api/market/search", json=self.query.model_dump())
        self.assertEqual(response.status_code, 200)
        result = response.json()
        expected = self.expected(self.query)
        self.assertEqual(result["source_city_count"], 11422)
        self.assertEqual(result["matching_summary"]["city_count"], 40)
        self.assertEqual(result["matching_summary"]["cluster_counts"], {"0": 9, "1": 22, "2": 9})
        self.assertEqual([r["city_id"] for r in result["items"]], [r["city_id"] for r in expected[:10]])
        self.assertAlmostEqual(result["matching_summary"]["mean_sector_share_percent"], statistics.mean(float(r["share_industry_2024"]) * 100 for r in expected))
        self.assertAlmostEqual(result["top_summary"]["mean_sector_share_percent"], statistics.mean(float(r["share_industry_2024"]) * 100 for r in expected[:10]))
        self.assertEqual(result["map"]["shown"], 40)
        self.assertEqual(result["top_summary"]["city_count"], 10)
        self.assertTrue(any(max(data.SECTORS, key=lambda s: float(r[f"share_{s}_2024"])) != "industry" for r in expected))

    def test_all_sort_orders_and_sectors_match_raw_csv_before_top_n(self):
        for sector in data.SECTORS:
            for sort_by in ["sector_share", "sector_emissions", "total_ghg"]:
                for order in ["asc", "desc"]:
                    with self.subTest(sector=sector, sort=sort_by, order=order):
                        query = market.MarketQuery(sector=sector, countries=["Japan", "Vietnam"], sort_by=sort_by, sort_order=order, limit=3)
                        result = market.search(query)
                        self.assertEqual([r["city_id"] for r in result["items"]], [r["city_id"] for r in self.expected(query)[:3]])
        global_result = market.search(market.MarketQuery(sector="energy", limit=100))
        self.assertEqual(global_result["matching_summary"]["city_count"], 11422)
        self.assertEqual(global_result["map"]["shown"], 5000)
        self.assertTrue(global_result["map"]["sampled"])

    def test_exact_share_boundary_and_cluster_zero(self):
        row = next(r for r in self.rows if r["city_id"] == "2007")
        share = float(row["share_industry_2024"]) * 100
        result = market.search(market.MarketQuery(sector="industry", countries=["United States"], cluster_id=0,
                                                 min_sector_share_percent=share, max_sector_share_percent=share))
        self.assertIn("2007", [r["city_id"] for r in result["items"]])
        self.assertEqual(result["matching_summary"]["cluster_counts"]["1"], 0)
        self.assertEqual(result["matching_summary"]["cluster_counts"]["2"], 0)

    def test_empty_results_and_no_report_api_call(self):
        query = market.MarketQuery(sector="industry", countries=["Japan"], min_sector_share_percent=100)
        result = market.search(query)
        self.assertEqual(result["items"], [])
        self.assertIsNone(result["matching_summary"]["mean_sector_share_percent"])
        self.assertEqual(result["map"]["points"], [])
        with patch.object(advisor._advisor(), "call_gemini", side_effect=AssertionError("No API for empty results")):
            self.assertEqual(self.client.post("/api/market/report", json={"query": query.model_dump()}).status_code, 422)

    def test_schema_country_normalization_and_rejects_arbitrary_fields(self):
        self.assertEqual(market.MarketQuery(sector="energy", countries=["Nhật Bản", " japan ", "VIỆT NAM"]).countries, ["Japan", "Vietnam"])
        bad = [{"sector": "sql"}, {"sort_by": "exec('malicious')"}, {"limit": 101}, {"limit": 0},
               {"limit": True}, {"cluster_id": 3}, {"countries": ["Atlantis"]}, {"countries": "Japan"},
               {"min_sector_share_percent": -1}, {"max_sector_share_percent": 101},
               {"min_sector_share_percent": 80, "max_sector_share_percent": 20}, {"sql": "SELECT *"}, {"region": "Asia"}]
        for payload in bad:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/market/search", json={"sector": "industry", **payload}).status_code, 422)
        with self.assertRaises(ValidationError):
            market.MarketQuery(sector="energy", min_sector_share_percent=float("nan"))

    def test_parse_returns_filters_and_flags_unverified_thresholds_for_revision(self):
        answer = {"query": self.query.model_dump(), "interpretation": "Ánh xạ công nghệ sơ bộ sang Công nghiệp.", "assumptions": [], "unsupported_criteria": []}
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer) as call, \
                patch.object(market, "search", side_effect=AssertionError("Parser must not query data")):
            response = self.client.post("/api/market/parse", json={"text": "Tìm 10 đô thị Nhật Bản có Công nghiệp từ 30% trở lên"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["query"]["min_sector_share_percent"], 30)
            self.assertEqual(call.call_args.kwargs["response_schema"], market.ParsedRequest.model_json_schema())
            self.assertIn("Japan", call.call_args.args[0]["available_countries"])
            response = self.client.post("/api/market/parse", json={"text": "Tôi kinh doanh thu hồi nhiệt. Tìm 10 đô thị Nhật Bản."})
            self.assertIsNone(response.json()["query"]["min_sector_share_percent"])
            self.assertTrue(response.json()["unsupported_criteria"])
        ranged = {**answer, "query": {**self.query.model_dump(), "min_sector_share_percent": 20, "max_sector_share_percent": 60}}
        with patch.object(advisor._advisor(), "call_gemini", return_value=ranged):
            response = self.client.post("/api/market/parse", json={"text": "Tìm đô thị Nhật Bản có tỷ trọng công nghiệp 20–60%"})
            self.assertEqual(response.json()["query"]["min_sector_share_percent"], 20)
            self.assertEqual(response.json()["query"]["max_sector_share_percent"], 60)
        for region in ["châu Á", "châu Âu", "ASEAN", "North America"]:
            with patch.object(advisor._advisor(), "call_gemini", side_effect=AssertionError("No invented regional country list")):
                self.assertEqual(self.client.post("/api/market/parse", json={"text": f"Tìm đô thị ở {region}"}).status_code, 422)

    def test_csv_export_contains_the_exact_ranked_real_rows_for_both_scopes(self):
        for scope in ["top", "matching"]:
            response = self.client.post("/api/market/export", json={"query": self.query.model_dump(), "scope": scope})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            rows = list(csv.DictReader(io.StringIO(body["csv"].lstrip("\ufeff"))))
            expected = self.expected(self.query)[:10] if scope == "top" else self.expected(self.query)
            self.assertEqual(len(rows), body["row_count"])
            self.assertEqual([r["city_id"] for r in rows], [r["city_id"] for r in expected])
            for row, source in zip(rows, expected):
                self.assertEqual(float(row["sector_emissions_original_edgar_unit"]), float(source["ghg_industry_2024"]))

    def test_report_recomputes_and_validates_grounded_context(self):
        request = market.ReportRequest(query=self.query, business_request="Tôi cung cấp thu hồi nhiệt công nghiệp.")
        context = market.report_context(request)
        self.assertEqual(context["matching_summary"]["city_count"], 40)
        self.assertEqual(context["top_summary"]["city_count"], 10)
        self.assertEqual(len(context["representative_cities"]), 3)
        allowed = {r["city_id"] for r in self.expected(self.query)[:10]}
        self.assertTrue(all(c["city_id"] in allowed for c in context["representative_cities"]))
        with patch.object(data, "solutions_catalog", side_effect=AssertionError("No catalog")), \
                patch.object(advisor._advisor(), "call_gemini", return_value=self.report_fixture(context)) as call:
            response = self.client.post("/api/market/report", json=request.model_dump())
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(call.call_args.args[0], context)
            self.assertEqual(call.call_args.kwargs["system_rules"], market.REPORT_RULES)
        localized = self.report_fixture(context)
        localized["emissions_profile"] += " Ngành `share_industry_2024`, toàn bộ dữ liệu gốc có 11.422 đô thị."
        with patch.object(advisor._advisor(), "call_gemini", return_value=localized):
            report = market.generate_report(request)["report"]
            self.assertIn("Công nghiệp", report["emissions_profile"])
            self.assertNotIn("industry", report["emissions_profile"])
            self.assertIn("11.422", report["emissions_profile"])
        one = market.ReportRequest(query=market.MarketQuery(**{**self.query.model_dump(), "limit": 1}))
        single_context = market.report_context(one)
        self.assertEqual(len(single_context["representative_cities"]), 1)
        with patch.object(advisor._advisor(), "call_gemini", return_value=self.report_fixture(single_context)):
            self.assertEqual(len(market.generate_report(one)["report"]["city_comparisons"]), 1)
        self.assertEqual(self.client.post("/api/market/report", json={**request.model_dump(), "matching_summary": {"city_count": 999999}}).status_code, 422)

    def test_report_rejects_invented_numbers_ids_empty_sections_and_masks_errors(self):
        request = market.ReportRequest(query=self.query)
        context = market.report_context(request)
        answer = self.report_fixture(context)
        for invalid in [{**answer, "research_request": answer["research_request"] + " Có 999999 khách hàng."},
                        {**answer, "city_comparisons": [{"city_id": "not-provided", "text": "Đô thị không tồn tại trong đầu vào."}]},
                        {**answer, "limitations": "   "}]:
            with patch.object(advisor._advisor(), "call_gemini", return_value=invalid):
                self.assertEqual(self.client.post("/api/market/report", json=request.model_dump()).status_code, 502)
        with patch.object(advisor._advisor(), "call_gemini", side_effect=RuntimeError("HTTP 503 secret-key")):
            response = self.client.post("/api/market/report", json=request.model_dump())
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("secret-key", response.text)
        market.render_verified_text("Toàn bộ dữ liệu gốc có 11.422 đô thị. Tập phù hợp có tỷ trọng trung bình 47,06%.", "emissions_profile", context)


if __name__ == "__main__":
    unittest.main()
