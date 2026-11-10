"""Business context is not a buyer-data filter. Gemini is mocked, EDGAR is real."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import advisor_service as advisor, market_service as market
from api.main import app


class MarketBusinessParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def parse(self, text, query=None, unsupported=None, **fields):
        answer = {"query": query or market.MarketQuery(sector="energy").model_dump(),
                  "interpretation": "Cách hiểu của Gemini.", "assumptions": [],
                  "unsupported_criteria": unsupported or [], **fields}
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer) as call:
            response = self.client.post("/api/market/parse", json={"text": text})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), call

    def test_solar_lamp_sales_intent_in_vietnam_is_general_exploration(self):
        parsed, call = self.parse("Tôi muốn bán đèn năng lượng mặt trời ở Việt Nam.",
            unsupported=["Lọc theo nhu cầu mua hàng, ngân sách hoặc quy mô doanh thu."])
        self.assertEqual(parsed["business_goal"], "muốn bán")
        self.assertEqual(parsed["product"], "đèn năng lượng mặt trời")
        self.assertEqual(parsed["query"], market.MarketQuery(sector="all", countries=["Vietnam"], sort_by="total_ghg").model_dump())
        self.assertEqual(parsed["sector_basis"], "general_exploration")
        self.assertEqual(parsed["unsupported_criteria"], [])
        self.assertIsNone(parsed["query"]["min_sector_share_percent"])
        self.assertEqual(call.call_args.args[0]["recognized_business_context"]["countries"], ["Vietnam"])
        self.assertIn("business_goal", call.call_args.kwargs["response_schema"]["properties"])
        result = self.client.post("/api/market/search", json=parsed["query"])
        self.assertEqual(result.status_code, 200)
        self.assertGreater(result.json()["matching_summary"]["city_count"], 0)
        self.assertTrue(all(city["country_name"] == "Vietnam" for city in result.json()["items"]))
        self.assertNotIn("buyer_count", result.json())

    def test_explicit_energy_threshold_remains_a_data_filter(self):
        query = market.MarketQuery(sector="energy", countries=["Vietnam"], min_sector_share_percent=30).model_dump()
        parsed, _ = self.parse("Tìm 10 đô thị tại Việt Nam có tỷ trọng năng lượng trên 30%", query=query,
                               sector_basis="explicit_filter")
        self.assertEqual(parsed["unsupported_criteria"], [])
        self.assertEqual(parsed["query"], query)
        result = market.search(market.MarketQuery.model_validate(parsed["query"]))
        expected = market.search(market.MarketQuery.model_validate(query))
        self.assertEqual(result, expected)
        self.assertTrue(all(city["sector_share_percent"] >= 30 for city in result["items"]))

    def test_waste_treatment_sales_in_japan_does_not_invent_sector_or_buyers(self):
        parsed, _ = self.parse("Tôi muốn bán công nghệ xử lý rác ở Nhật Bản",
                                unsupported=["Không có dữ liệu về nhu cầu mua công nghệ."])
        self.assertEqual(parsed["product"], "công nghệ xử lý rác")
        self.assertEqual(parsed["query"]["countries"], ["Japan"])
        self.assertEqual(parsed["query"]["sector"], "all")
        self.assertEqual(parsed["query"]["sort_by"], "total_ghg")
        self.assertEqual(parsed["unsupported_criteria"], [])

    def test_ranking_by_buyers_is_unsupported_even_if_gemini_omits_warning(self):
        for unsupported in [[], ["Yêu cầu tìm kiếm theo cấp độ đô thị không được hỗ trợ."]]:
            with self.subTest(unsupported=unsupported):
                parsed, _ = self.parse("Tìm 10 thành phố có nhiều khách hàng muốn mua đèn nhất", unsupported=unsupported)
                self.assertTrue(parsed["unsupported_criteria"])
                self.assertIn("khách hàng", parsed["unsupported_criteria"][0])

    def test_real_commercial_filters_are_not_replaced_by_ghg(self):
        for text in ["Tìm 10 đô thị có doanh số đèn năng lượng mặt trời cao nhất",
                     "Tìm đô thị tại Việt Nam có ngân sách mua đèn trên một tỷ đồng",
                     "Tôi muốn bán đèn ở Việt Nam. Tìm 10 đô thị có thị phần đèn cao nhất",
                     "Tìm các đô thị có doanh thu đèn cao nhất"]:
            with self.subTest(text=text):
                parsed, _ = self.parse(text)
                self.assertTrue(parsed["unsupported_criteria"])
                self.assertIsNone(market._simple_business_exploration(text))

    def test_other_business_goal_forms_and_open_ended_products(self):
        for text, product in [("Tôi đang kinh doanh thiết bị xử lý chất thải tại Việt Nam.", "thiết bị xử lý chất thải"),
                              ("Tôi muốn tìm thị trường cho công nghệ tiết kiệm năng lượng ở Nhật Bản.", "công nghệ tiết kiệm năng lượng")]:
            with self.subTest(text=text):
                parsed, _ = self.parse(text, unsupported=["Không thể xác định khách hàng mua sản phẩm."])
                self.assertEqual(parsed["product"], product)
                self.assertEqual(parsed["unsupported_criteria"], [])
                self.assertEqual(parsed["query"]["sector"], "all")

    def test_simple_sales_normalization_never_swallows_filters_or_unknown_countries(self):
        for text in ["Tôi muốn bán đèn tại Atlantis", "Tôi muốn bán đèn ở Việt Nam có ngân sách cao nhất",
                     "Tôi muốn bán đèn và tìm 10 đô thị có tỷ trọng năng lượng từ 30% ở Việt Nam",
                     "Tôi muốn bán đèn ở Việt Nam, ưu tiên đô thị có nhiều khách hàng muốn mua"]:
            with self.subTest(text=text):
                self.assertIsNone(market._simple_business_exploration(text))

    def test_mixed_business_context_and_ghg_filters_are_preserved(self):
        query = market.MarketQuery(sector="waste", countries=["Japan"], cluster_id=0,
                                   min_sector_share_percent=5, limit=20).model_dump()
        parsed, _ = self.parse("Tôi muốn bán công nghệ xử lý rác. Tìm 20 đô thị ở Nhật Bản thuộc cụm 0 có tỷ trọng chất thải từ 5%",
                               query=query, business_goal="muốn bán", product="công nghệ xử lý rác", sector_basis="explicit_filter")
        self.assertEqual(parsed["query"], query)
        self.assertEqual(parsed["unsupported_criteria"], [])

    def test_business_growth_goals_and_negated_metrics_are_not_filter_requests(self):
        for text in ["Tôi muốn tăng doanh thu và tìm đô thị ở Việt Nam theo tổng GHG",
                     "Tìm đô thị theo tổng GHG, không cần lọc theo ngân sách",
                     "Tìm đô thị nhưng không yêu cầu doanh số",
                     "Tôi muốn tìm thị trường cho phần mềm quản lý ngân sách ở Việt Nam"]:
            with self.subTest(text=text):
                self.assertIsNone(market._commercial_filter_warning(text))
                parsed, _ = self.parse(text)
                self.assertEqual(parsed["unsupported_criteria"], [])


if __name__ == "__main__":
    unittest.main()
