"""Numeric claims must match the right source fact, not any number in a whitelist."""
import csv
import statistics
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import advisor_service as advisor, data_service as data, market_service as market
from api.market_facts import FactValidationError, render_verified_text
from api.main import app
import test_market_explorer as fixtures


class MarketFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = market.ReportRequest(query=market.MarketQuery(sector="industry", countries=["Japan"], min_sector_share_percent=30))
        cls.context = market.report_context(cls.request)
        cls.facts = cls.context["verified_facts"]
        cls.client = TestClient(app)

    def render(self, text, path="research_request", city_id=None):
        return render_verified_text(text, path, self.context, city_id)[0]

    def test_facts_values_and_provenance_match_independent_raw_csv(self):
        with data.CITY_PATH.open(encoding="utf-8-sig", newline="") as handle:
            rows = [r for r in csv.DictReader(handle) if r["country_name"] == "Japan" and float(r["share_industry_2024"]) * 100 >= 30]
        ordered = sorted(rows, key=lambda r: (-float(r["ghg_industry_2024"]), r["city_id"]))
        self.assertEqual(self.facts["matching.city_count"]["value"], len(rows))
        self.assertEqual(self.facts["top.city_count"]["value"], 10)
        self.assertEqual(self.facts["matching.mean_sector_share_percent"]["value"], statistics.fmean(float(r["share_industry_2024"]) * 100 for r in rows))
        self.assertEqual(self.facts["top.mean_sector_share_percent"]["value"], statistics.fmean(float(r["share_industry_2024"]) * 100 for r in ordered[:10]))
        for i in (0, 5, 9):
            row = ordered[i]
            prefix = f"cities.{row['city_id']}"
            self.assertEqual(self.facts[prefix + ".rank"]["value"], i + 1)
            gap = float(row["share_industry_2024"]) * 100 - self.facts["matching.mean_sector_share_percent"]["value"]
            self.assertAlmostEqual(self.facts[prefix + ".share_gap_matching_pp"]["value"], gap)
        self.assertTrue(all(fact["source"] and fact["scope"] for fact in self.facts.values()))

    def test_exact_and_rounded_literals_render_canonical_python_values(self):
        for value in ["47,06%", "47.06%", "47,1%", "47.1%", "47%"]:
            self.assertEqual(self.render(f"Tập phù hợp có tỷ trọng trung bình {value}."), "Tập phù hợp có tỷ trọng trung bình 47,06%.")
        for value in ["11.422", "11,422", "11 422", "11422"]:
            self.assertEqual(self.render(f"Toàn bộ dữ liệu gốc có {value} đô thị."), "Toàn bộ dữ liệu gốc có 11.422 đô thị.")
        # A percentage with three decimal digits is not a thousands-grouped city count.
        self.assertEqual(self.render("Tỷ trọng tối thiểu 30.000%."), "Tỷ trọng tối thiểu 30,00%.")
        self.assertEqual(self.render("Tỷ trọng tối thiểu 30,000%."), "Tỷ trọng tối thiểu 30,00%.")

    def test_swapping_full_match_and_top_n_is_rejected_with_specific_diagnostics(self):
        for text, key, observed, expected in [
            ("Top N có 40 đô thị.", "top.city_count", "40", "10"),
            ("Toàn bộ tập phù hợp có 10 đô thị.", "matching.city_count", "10", "40"),
            ("Top N có tỷ trọng trung bình 47,06%.", "top.mean_sector_share_percent", "47.06", "60,61%")]:
            with self.subTest(text=text), self.assertRaises(FactValidationError) as caught:
                self.render(text)
            error = caught.exception.details
            self.assertEqual((error["fact_id"], error["observed"], error["expected"]), (key, observed, expected))
            self.assertEqual(error["field_path"], "research_request")
            self.assertEqual(error["rule"], "value_mismatch")

    def test_cluster_ids_year_model_and_real_cluster_counts_have_distinct_roles(self):
        text = "Cụm 0; Cụm 1; Cụm 2; năm 2024; K=3."
        self.assertEqual(self.render(text), text)
        self.assertEqual(self.render("Các cụm 0, 1 và 2; năm 2024."), "Các cụm 0, 1 và 2; năm 2024.")
        self.assertEqual(self.render("Các cụm 0,1,2."), "Các cụm 0,1,2.")
        self.assertEqual(self.render("Toàn bộ tập phù hợp: Cụm 1 có 22 đô thị."), "Toàn bộ tập phù hợp: Cụm 1 có 22 đô thị.")
        self.assertEqual(self.render("Top N: Cụm 1 có 6 đô thị."), "Top N: Cụm 1 có 6 đô thị.")
        for text in ["Năm 3.", "Cụm 2024.", "Các cụm 0, 1 và 2024.", "Top N: Cụm 1 có 22 đô thị."]:
            with self.subTest(text=text), self.assertRaises(FactValidationError):
                self.render(text)

    def test_rank_is_bound_to_the_compared_city_and_actual_top_n(self):
        for city in self.context["representative_cities"]:
            text = f"Trong Top10, đô thị đứng thứ hạng {city['rank_in_top']}."
            rendered = self.render(text, "city_comparisons.0.text", city["city_id"])
            self.assertIn(f"thứ hạng {city['rank_in_top']}", rendered)
        first = self.context["representative_cities"][0]
        with self.assertRaises(FactValidationError) as caught:
            self.render("Đô thị đứng thứ hạng 6.", "city_comparisons.0.text", first["city_id"])
        self.assertEqual(caught.exception.details["fact_id"], f"cities.{first['city_id']}.rank")
        self.assertEqual(caught.exception.details["expected"], "1")

    def test_references_are_rendered_and_cannot_change_scope_or_invent_facts(self):
        text = "Toàn bộ tập phù hợp có {{matching.city_count}} đô thị; Top N có {{top.city_count}} đô thị."
        self.assertEqual(self.render(text), "Toàn bộ tập phù hợp có 40 đô thị; Top N có 10 đô thị.")
        self.assertEqual(self.render("Tập phù hợp: Cụm {{model.cluster_ids.1}} có {{matching.clusters.1.city_count}} đô thị."), "Tập phù hợp: Cụm 1 có 22 đô thị.")
        self.assertEqual(self.render("Tỷ trọng trung bình {{matching.mean_sector_share_percent}}%."), "Tỷ trọng trung bình 47,06%.")
        for text in ["Top N có {{matching.city_count}} đô thị.", "Năm {{model.k}}.", "Có {{PRIVATE_SECRET123}} đô thị.", "Tỷ trọng trung bình {{matching.city_count}}."]:
            with self.subTest(text=text), self.assertRaises(FactValidationError):
                self.render(text)
        cities = self.context["representative_cities"]
        with self.assertRaises(FactValidationError):
            self.render("Chênh lệch {{comparisons." + cities[0]["city_id"] + "." + cities[1]["city_id"] + ".share_gap_pp}}.",
                        "city_comparisons.2.text", cities[2]["city_id"])

    def test_unsupported_market_claims_unbound_numbers_and_notation(self):
        for text in ["Có 999999 khách hàng cam kết mua.", "Lợi nhuận 2024%.", "1e6 khách hàng.", "47,06%"]:
            with self.subTest(text=text), self.assertRaises(FactValidationError):
                self.render(text)
        self.assertEqual(self.render("Không chuyển đơn vị sang tCO₂e."), "Không chuyển đơn vị sang tCO₂e.")

    def test_valid_city_cluster_then_sector_share_is_not_a_cluster_population_rate(self):
        city = self.context["representative_cities"][0]
        prefix = f"cities.{city['city_id']}"
        raw = city["city_name"] + " thuộc Cụm {{" + prefix + ".cluster_id}}, có tỷ trọng Công nghiệp {{" + prefix + ".sector_share_percent}}."
        rendered = self.render(raw, "emissions_profile")
        self.assertIn(self.facts[prefix + ".sector_share_percent"]["display"], rendered)
        literal = f"{city['city_name']} thuộc Cụm {city['cluster_id']}, có tỷ trọng Công nghiệp {city['sector_share_percent']:.2f}%."
        self.assertEqual(self.render(literal, "emissions_profile"), rendered)
        wrong_id = (city["cluster_id"] + 1) % 3
        with self.assertRaises(FactValidationError):
            self.render(city["city_name"] + " thuộc Cụm {{model.cluster_ids." + str(wrong_id) + "}}.", "emissions_profile")

    def test_reference_spacing_and_display_path_aliases_only_resolve_known_facts(self):
        for token in ["{{ matching.city_count }}", "{{ verified_facts.matching.city_count }}", "{{ verified_facts.matching.city_count.display }}", "{{matching.city_count.value}}"]:
            self.assertEqual(self.render("Tập phù hợp có " + token + " đô thị."), "Tập phù hợp có 40 đô thị.")
        with self.assertRaises(FactValidationError):
            self.render("Top N có {{ verified_facts.matching.city_count.display }} đô thị.")
        with self.assertRaises(FactValidationError):
            self.render("Có {{ verified_facts.SECRET_API_KEY.value }} đô thị.")

    def test_api_attaches_python_facts_and_logs_only_targeted_mismatches(self):
        report = fixtures.MarketExplorerTests.report_fixture(self.context)
        report["research_request"] = "Top N có 40 đô thị. PRIVATE_REPORT_BODY"
        with patch.object(advisor._advisor(), "call_gemini", return_value=report) as call, self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
            response = self.client.post("/api/market/report", json=self.request.model_dump())
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()["validation"]["field_path"], "research_request")
            self.assertEqual(response.json()["validation"]["observed"], "40")
            self.assertEqual(response.json()["validation"]["expected"], "10")
            self.assertIn("research_request", response.json()["detail"])
            self.assertEqual(call.call_count, 2)
            text = "\n".join(logs.output)
            for token in ['"field_path": "research_request"', '"fact_id": "top.city_count"', '"expected": "10"', '"observed": "40"']:
                self.assertIn(token, text)
            self.assertNotIn("PRIVATE_REPORT_BODY", text)
        report["research_request"] = "Toàn bộ tập phù hợp có {{matching.city_count}} đô thị; Top N có {{top.city_count}} đô thị."
        with patch.object(advisor._advisor(), "call_gemini", return_value=report):
            response = self.client.post("/api/market/report", json=self.request.model_dump())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["verified_facts"], self.facts)
        self.assertEqual(body["report"]["research_request"], "Toàn bộ tập phù hợp có 40 đô thị; Top N có 10 đô thị.")
        self.assertTrue(any(r["fact_id"] == "top.city_count" for r in body["numeric_references"]))
        self.assertNotIn("{{", body["report"]["research_request"])
        forged = {**report, "verified_facts": {"top.city_count": {"value": 40}}}
        with patch.object(advisor._advisor(), "call_gemini", return_value=forged), self.assertLogs(market.REPORT_LOG.name, level="INFO"):
            response = self.client.post("/api/market/report", json=self.request.model_dump())
        self.assertEqual((response.status_code, response.json()["error_code"]), (502, "report_schema"))


if __name__ == "__main__":
    unittest.main()
