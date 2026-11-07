"""Real CSV geometry checks and mocked Gemini; no external API calls."""
import csv
import json
import math
import statistics
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import advisor_service as advisor, data_service as data
from api.main import app


class CityExplorerTests(unittest.TestCase):
    CITIES = [("5213", "Nagoya", "Japan", 2),
              ("11345", "Shanghai", "China", 1),
              ("2007", "Los Angeles", "United States", 0)]

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        with data.CITY_PATH.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))
        with (data.ROOT / "reports/cluster_analysis/cluster_centroids_2024.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.centers = {int(r["cluster_id"]): r for r in csv.DictReader(handle)}

    @staticmethod
    def report_fixture():
        return {
            "summary": "Hồ sơ đô thị thể hiện cơ cấu phân bổ khí nhà kính giữa các lĩnh vực trong năm nghiên cứu. Các lĩnh vực có tỷ trọng nổi bật giúp mô tả đặc điểm tương đối của đô thị, nhưng không cho biết nguyên nhân hình thành cơ cấu đó. Việc đọc các tỷ trọng cùng lượng phát thải tuyệt đối cần giữ nguyên đơn vị gốc chưa được xác minh.",
            "comparisons": [
                "Các chênh lệch nổi bật so với tâm mô hình cho biết điểm khác biệt trong cơ cấu của đô thị. Cần đọc chúng cùng trung vị và độ phân tán của những thành viên cùng cụm, thay vì coi tâm là một hồ sơ áp dụng cho mọi thành viên.",
                "Những lĩnh vực gần tâm hơn có thể mô tả điểm tương đồng về cấu trúc. Tuy nhiên, sự giống nhau về tỷ trọng không đồng nghĩa với cùng quy mô phát thải hoặc cùng điều kiện địa phương."],
            "dispersion_and_representativeness": "Vị trí khoảng cách được tính trong đúng cụm đô thị. Nó mô tả tỷ lệ thành viên có khoảng cách không lớn hơn đô thị đang xem, kể cả chính đô thị và các khoảng cách bằng nhau. Giá trị này là mô tả thực nghiệm, không phải xác suất, kiểm định thống kê hay kết luận ngoại lệ. Tâm chỉ tóm tắt một cấu trúc chung của nhóm.",
            "research_questions": ["Các lĩnh vực có chênh lệch lớn nhất đóng vai trò thế nào trong sự khác biệt cơ cấu của đô thị?", "Cơ cấu đô thị có ổn định qua thời gian không? Cần bổ sung dữ liệu các năm ngoài năm 2024 để nghiên cứu."],
            "limitations": ["K=3 cố định và dữ liệu chỉ phản ánh năm 2024. Không thể suy luận nguyên nhân phát thải, chất lượng môi trường, nhu cầu thị trường hoặc tính khả thi công nghệ chỉ từ các tỷ trọng GHG."]}

    def test_three_real_cities_against_raw_csv(self):
        for city_id, name, country, cid in self.CITIES:
            with self.subTest(city=name):
                response = self.client.get(f"/api/cities/{city_id}")
                self.assertEqual(response.status_code, 200)
                details = response.json()
                profile = details["analysis"]
                self.assertEqual((profile["city_name"], profile["country_name"], profile["cluster_id"]), (name, country, cid))
                row = next(r for r in self.rows if r["city_id"] == city_id)
                peers = [r for r in self.rows if int(r["cluster_id"]) == cid]
                self.assertAlmostEqual(sum(profile["shares_percent"].values()), 100, places=8)
                self.assertAlmostEqual(sum(profile["emissions_by_sector"].values()), float(row["ghg_total_2024"]), places=6)
                for sector in data.SECTORS:
                    share = float(row[f"share_{sector}_2024"]) * 100
                    center = float(self.centers[cid][f"share_{sector}_2024"]) * 100
                    self.assertEqual(profile["emissions_by_sector"][sector], float(row[f"ghg_{sector}_2024"]))
                    self.assertEqual(profile["shares_percent"][sector], share)
                    self.assertAlmostEqual(profile["comparison_to_centroid_pp"][sector], share - center, places=12)
                    values = [float(r[f"share_{sector}_2024"]) * 100 for r in peers]
                    stats = profile["cluster"]["sector_statistics_percent"][sector]
                    self.assertAlmostEqual(stats["mean"], statistics.mean(values))
                    self.assertAlmostEqual(stats["median"], statistics.median(values))
                    self.assertAlmostEqual(stats["std"], statistics.pstdev(values))
                    quartiles = statistics.quantiles(values, method="inclusive")
                    self.assertAlmostEqual(stats["iqr"], quartiles[2] - quartiles[0])
                distance = math.sqrt(sum((float(row[f"share_{s}_2024"]) - float(self.centers[cid][f"share_{s}_2024"])) ** 2 for s in data.SECTORS))
                self.assertAlmostEqual(profile["distance_to_centroid"], distance, places=12)
                position = profile["position_in_cluster"]
                count = sum(float(r["distance_to_centroid"]) <= float(row["distance_to_centroid"]) for r in peers)
                self.assertEqual(position["reference_city_count"], len(peers))
                self.assertEqual(position["count_at_or_below"], count)
                self.assertAlmostEqual(position["percentile_rank_percent"], 100 * count / len(peers))
                if distance < profile["cluster"]["distance_statistics"]["median"]:
                    self.assertIn("nhỏ hơn trung vị", position["summary"])
                else:
                    self.assertIn("lớn hơn trung vị", position["summary"])
                top = sorted(data.SECTORS, key=lambda s: abs(profile["comparison_to_centroid_pp"][s]), reverse=True)[:3]
                self.assertEqual([item["sector"] for item in profile["notable_differences"]], top)
                # Existing consumers retain their mean-based comparison contract.
                for s in data.SECTORS:
                    self.assertEqual(details["comparison_percentage_points"][s], round(details["shares_percent"][s] - details["cluster"]["mean_sector_shares_percent"][s], 4))

    def test_empirical_percentile_extremes_include_self_and_ties(self):
        for cid in range(3):
            peers = [r for r in self.rows if int(r["cluster_id"]) == cid]
            for row in [min(peers, key=lambda r: float(r["distance_to_centroid"])), max(peers, key=lambda r: float(r["distance_to_centroid"]))]:
                position = data.city_analysis(row["city_id"])["position_in_cluster"]
                expected = sum(float(r["distance_to_centroid"]) <= float(row["distance_to_centroid"]) for r in peers)
                self.assertEqual(position["count_at_or_below"], expected)
                self.assertGreater(position["percentile_rank_percent"], 0)
            self.assertEqual(position["percentile_rank_percent"], 100)

    def test_normalized_gemini_payload_without_solutions_catalog(self):
        original = json.dumps(data.cluster_explorer(), sort_keys=True)
        module = advisor._advisor()
        answer = self.report_fixture()
        with patch.object(data, "solutions_catalog", side_effect=AssertionError("Catalog forbidden")), \
                patch.object(module, "prepare_context", side_effect=AssertionError("Legacy solution context forbidden")), \
                patch.object(module, "call_gemini", return_value=answer) as call:
            for city_id, _, _, cid in self.CITIES:
                response = self.client.post(f"/api/cities/{city_id}/interpret", json={})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["city_id"], city_id)
                self.assertEqual(response.json()["cluster_id"], cid)
                context = call.call_args.args[0]
                profile = data.city_analysis(city_id)
                self.assertEqual(context, advisor.city_preview(city_id))
                self.assertEqual(context["sector_labels"], data.SECTOR_LABELS)
                self.assertEqual(context["top_sector_labels"], [data.SECTOR_LABELS[s] for s in profile["top_sectors"]])
                for difference in context["notable_differences"]:
                    self.assertEqual(difference["sector_label"], data.SECTOR_LABELS[difference["sector"]])
                for s in data.SECTORS:
                    self.assertEqual(context["shares_percent"][s], round(profile["shares_percent"][s], 2))
                    # Round only AFTER calculating the full-precision difference.
                    self.assertEqual(context["comparison_to_centroid_pp"][s], round(profile["comparison_to_centroid_pp"][s], 2))
                self.assertEqual(context["distance_to_centroid"], round(profile["distance_to_centroid"], 4))
                self.assertEqual(context["position_in_cluster"]["percentile_rank_percent"], round(profile["position_in_cluster"]["percentile_rank_percent"], 2))
                for key, value in context["cluster"]["distance_statistics"].items():
                    self.assertEqual(value, round(profile["cluster"]["distance_statistics"][key], 4))
                self.assertNotIn("catalog_solutions", context)
                self.assertEqual(call.call_args.kwargs["system_rules"], advisor.CITY_RULES)
                self.assertEqual(call.call_args.kwargs["response_schema"], advisor.ClusterInterpretation.model_json_schema())
        self.assertEqual(json.dumps(data.cluster_explorer(), sort_keys=True), original)

    def test_city_report_translates_sector_codes_in_all_sections(self):
        answer = self.report_fixture()
        answer["summary"] = "agriculture, ENERGY, industry, international, residential, transport, waste. " + answer["summary"]
        answer["comparisons"][0] += " `share_industry_2024` và ghg_energy_2024."
        answer["dispersion_and_representativeness"] += " residential và transport."
        answer["research_questions"][0] += " agriculture?"
        answer["limitations"][0] += " waste."
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer):
            response = self.client.post("/api/cities/5213/interpret", json={})
        self.assertEqual(response.status_code, 200, response.text)
        translated = response.json()["report"]
        text = json.dumps(translated, ensure_ascii=False)
        for sector, label in data.SECTOR_LABELS.items():
            self.assertNotIn(sector, text.lower())
            self.assertIn(label, text)
        self.assertIn("Công nghiệp và Năng lượng", translated["comparisons"][0])
        # The city-only normalization must not alter Cluster Explorer behavior.
        self.assertIn("industry", advisor._validated_cluster_report(answer)["summary"])

    def test_city_report_checks_length_after_translation(self):
        answer = self.report_fixture()
        other_words = sum(len(text.split()) for key, value in answer.items() if key != "summary"
                          for text in (value if isinstance(value, list) else [value]))
        answer["summary"] = "industry " * (399 - other_words)
        advisor._validated_cluster_report(answer)  # Within the original 250–400-word range.
        with self.assertRaises(ValueError):
            advisor._validated_city_report(answer)  # Vietnamese labels expand the word count.

    def test_search_and_country_filter(self):
        for city_id, name, country, cid in self.CITIES:
            result = self.client.get("/api/cities", params={"search": name, "country": country}).json()
            self.assertTrue(any(c["city_id"] == city_id and c["cluster_id"] == cid for c in result["items"]))
        result = self.client.get("/api/cities", params={"search": "Nagoya", "country": "China"}).json()
        self.assertEqual(result["total"], 0)

    def test_missing_city_never_calls_gemini(self):
        with patch.object(advisor._advisor(), "call_gemini", side_effect=AssertionError("Must not call")):
            self.assertEqual(self.client.get("/api/cities/missing").status_code, 404)
            self.assertEqual(self.client.post("/api/cities/missing/interpret", json={}).status_code, 404)

    def test_provider_and_invalid_report_errors_are_safe(self):
        module = advisor._advisor()
        for error in ["Chưa đặt GEMINI_API_KEY", "HTTP 503 secret-key-provider-response"]:
            with patch.object(module, "call_gemini", side_effect=RuntimeError(error)):
                response = self.client.post("/api/cities/5213/interpret", json={})
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret-key-provider-response", response.text)
        for report in [{}, {**self.report_fixture(), "summary": "từ " * 401}]:
            with patch.object(module, "call_gemini", return_value=report):
                self.assertEqual(self.client.post("/api/cities/5213/interpret", json={}).status_code, 503)

    def test_inconsistent_emissions_rejected(self):
        original = data._read_csv
        def corrupted(path):
            rows = original(path)
            if path == data.CITY_PATH:
                next(r for r in rows if r["city_id"] == "5213")["ghg_total_2024"] = "nan"
            return rows
        data._city_analysis_inputs.cache_clear()
        try:
            with patch.object(data, "_read_csv", side_effect=corrupted):
                with self.assertRaisesRegex(ValueError, "Phát thải"):
                    data.city_analysis("5213")
        finally:
            data._city_analysis_inputs.cache_clear()


if __name__ == "__main__":
    unittest.main()
