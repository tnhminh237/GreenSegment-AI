"""Browser integration checks. Start Vite, then run python tests/ui_market_search.py.

Uses installed Chrome and the real FastAPI query engine through intercepted /api
requests. Only Gemini responses are mocked; no credentials or external API calls.
Requires Python playwright. Override MARKET_UI_URL / MARKET_CHROME if needed.
"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from api import advisor_service as advisor, market_service as market
from api.main import app
import test_market_explorer as fixtures


class MarketSearchBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=os.environ.get("MARKET_CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            headless=True,
        )
        cls.api = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
        self.page = self.context.new_page()
        self.page_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.calls = []
        self.parse_failure = False
        self.unsupported = []
        self.defer_parse = False
        self.held_parse = None
        self.parsed_query = market.MarketQuery(sector="industry", countries=["Japan"],
                                                min_sector_share_percent=30).model_dump()
        self.page.route("**/api/**", self.api_route)
        self.page.route("https://*.tile.openstreetmap.org/**", lambda route: route.abort())
        self.page.goto(os.environ.get("MARKET_UI_URL", "http://127.0.0.1:5174"))
        self.page.get_by_role("button", name="Market Explorer", exact=True).click()
        expect(self.page.locator("#market-request")).to_be_visible()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.page_errors, [])

    def api_route(self, route):
        request = route.request
        path = request.url.split("/api", 1)[1]
        payload = request.post_data_json if request.method == "POST" else None
        self.calls.append((path, payload))
        if path == "/market/parse":
            if self.defer_parse:
                self.held_parse = route
                return
            if self.parse_failure:
                with patch.object(advisor._advisor(), "call_gemini", side_effect=RuntimeError("Chưa đặt GEMINI_API_KEY")):
                    response = self.api.post("/api" + path, json=payload)
            else:
                parsed = {"query": self.parsed_query, "interpretation": "Phạm vi nghiên cứu.",
                          "assumptions": [], "unsupported_criteria": self.unsupported}
                with patch.object(advisor._advisor(), "call_gemini", return_value=parsed):
                    response = self.api.post("/api" + path, json=payload)
        elif path == "/market/report":
            context = market.report_context(market.ReportRequest.model_validate(payload))
            with patch.object(advisor._advisor(), "call_gemini", return_value=fixtures.MarketExplorerTests.report_fixture(context)):
                response = self.api.post("/api" + path, json=payload)
        else:
            # Searching must work even if the Gemini module cannot initialize.
            with patch.object(advisor, "_advisor", side_effect=AssertionError("No Gemini for search")):
                response = self.api.request(request.method, "/api" + path, **({"json": payload} if payload is not None else {}))
        route.fulfill(status=response.status_code, content_type="application/json", body=response.content)

    def manual(self):
        self.page.locator('.market-mode-switch button').nth(1).click()
        expect(self.page.locator("#market-request")).to_have_count(0)
        expect(self.page.locator("#market-sector")).to_be_visible()

    def search(self):
        self.page.locator('#market-search-panel button[type="submit"]').click()
        expect(self.page.locator(".market-results")).to_be_visible()

    def ids(self):
        return self.page.locator(".market-table tbody th").all_text_contents()

    def test_manual_offline_same_ai_query_and_report_for_both_modes(self):
        self.manual()
        self.page.locator("#market-countries").select_option(["Japan"])
        self.page.locator("#market-min").fill("30")
        self.search()
        manual_names = self.ids()
        expect(self.page.locator(".stat-card").first.locator("strong")).to_have_text("40")
        self.assertEqual(len(manual_names), 10)
        self.assertFalse(any(path == "/market/parse" for path, _ in self.calls))
        self.page.get_by_role("button", name="Tạo báo cáo thị trường bằng Gemini").click()
        expect(self.page.locator(".ce-report")).to_be_visible()
        self.assertEqual([p for route, p in self.calls if route == "/market/report"][-1]["business_request"], "")
        self.page.locator('.market-mode-switch button').first.click()
        expect(self.page.locator(".market-results")).to_have_count(0)
        expect(self.page.locator("#market-sector")).to_have_count(0)
        self.page.locator("#market-request").fill("Tìm 10 đô thị Nhật Bản có tỷ trọng công nghiệp từ 30%")
        self.search()
        self.assertEqual(self.ids(), manual_names)
        expect(self.page.locator(".market-applied")).to_contain_text("30%")
        self.assertEqual([p for path, p in self.calls if path == "/market/search"][-2:],
                         [self.parsed_query, self.parsed_query])
        expect(self.page.get_by_text("Cách hiểu sơ bộ", exact=False)).to_have_count(0)
        expect(self.page.locator('input[type="checkbox"]')).to_have_count(0)
        self.page.get_by_role("button", name="Tạo báo cáo thị trường bằng Gemini").click()
        expect(self.page.locator(".ce-report")).to_be_visible()
        self.page.locator("#market-request").fill("Yêu cầu mới chưa tìm kiếm")
        expect(self.page.locator(".market-results")).to_have_count(0)

    def test_unsupported_ai_request_blocks_search_and_can_be_revised(self):
        self.unsupported = ["Chưa có dữ liệu ngân sách mua sắm"]
        self.page.locator("#market-request").fill("Tìm đô thị có ngân sách mua sắm lớn")
        self.page.locator('#market-search-panel button[type="submit"]').click()
        expect(self.page.get_by_text("Chưa thể tìm kiếm.", exact=False)).to_be_visible()
        self.assertFalse(any(path == "/market/search" for path, _ in self.calls))
        self.unsupported = []
        self.page.locator("#market-request").fill("Tìm 10 đô thị Nhật Bản có tỷ trọng công nghiệp từ 30%")
        self.search()

    def test_solar_lamp_business_context_searches_vietnam_without_buyer_claims(self):
        self.unsupported = ["Lọc theo nhu cầu mua hàng, ngân sách hoặc quy mô doanh thu."]
        self.page.locator("#market-request").fill("Tôi muốn bán đèn năng lượng mặt trời ở Việt Nam.")
        self.search()
        expect(self.page.locator(".market-applied")).to_contain_text("đèn năng lượng mặt trời")
        expect(self.page.locator(".market-applied")).to_contain_text("Khám phá chung theo tổng GHG")
        query = [payload for path, payload in self.calls if path == "/market/search"][-1]
        self.assertEqual(query["countries"], ["Vietnam"])
        self.assertEqual(query["sector"], "all")
        self.assertEqual(query["sort_by"], "total_ghg")
        expect(self.page.locator(".market-table tbody tr")).to_have_count(10)
        self.assertTrue(all(country == "Vietnam" for country in self.page.locator(".market-table tbody td:first-of-type").all_text_contents()))

    def test_manual_still_works_after_gemini_failure(self):
        self.parse_failure = True
        self.page.locator("#market-request").fill("Tìm đô thị công nghiệp")
        self.page.locator('#market-search-panel button[type="submit"]').click()
        expect(self.page.get_by_text("Chưa đặt GEMINI_API_KEY", exact=False)).to_be_visible()
        self.manual()
        self.search()
        expect(self.page.locator(".market-table tbody tr")).to_have_count(10)

    def test_switching_mode_cancels_pending_ai_request(self):
        self.defer_parse = True
        self.page.locator("#market-request").fill("Tìm đô thị công nghiệp ở Nhật Bản")
        self.page.locator('#market-search-panel button[type="submit"]').click()
        expect(self.page.locator('#market-search-panel button[type="submit"]')).to_be_disabled()
        self.manual()
        self.assertIsNotNone(self.held_parse)
        expect(self.page.locator('#market-search-panel button[type="submit"]')).to_be_enabled()
        self.search()
        # Complete the held route after cancellation; this late response must not
        # start an AI search or overwrite the manual results.
        self.held_parse.fulfill(status=200, json={"query": self.parsed_query,
                                                "unsupported_criteria": [], "assumptions": [],
                                                "interpretation": "Phạm vi nghiên cứu."})
        expect(self.page.locator(".market-table tbody tr")).to_have_count(10)
        self.assertEqual([path for path, _ in self.calls if path.startswith("/market/")],
                         ["/market/parse", "/market/search"])

    def test_filters_stale_results_validation_reset_and_empty_state(self):
        self.manual()
        self.page.locator("#market-countries").select_option(["Japan"])
        self.page.locator("#market-min").fill("30")
        self.page.locator("#market-cluster").select_option("0")
        self.page.locator("#market-limit").select_option("5")
        self.search()
        expect(self.page.locator(".market-table tbody tr")).to_have_count(5)
        expect(self.page.locator(".stat-card").first.locator("strong")).to_have_text("9")
        self.page.locator("#market-sort").select_option("sector_share")
        expect(self.page.locator(".market-results")).to_have_count(0)
        self.search()
        shares = self.page.locator(".market-table tbody tr td:nth-child(4)").all_text_contents()
        values = [float(v.replace("%", "").replace(",", ".")) for v in shares]
        self.assertEqual(values, sorted(values, reverse=True))
        for n in [10, 20, 50]:
            self.page.locator("#market-limit").select_option(str(n))
            self.search()
            expect(self.page.locator(".market-table tbody tr")).to_have_count(9)
        self.page.locator("#market-min").fill("101")
        before = len(self.calls)
        self.page.locator('#market-search-panel button[type="submit"]').click()
        self.assertFalse(self.page.locator("#market-min").evaluate("el => el.checkValidity()"))
        self.assertEqual(len(self.calls), before)
        self.page.locator("#market-min").fill("100")
        self.search()
        expect(self.page.get_by_text("Không có đô thị đáp ứng tiêu chí.", exact=False)).to_be_visible()
        expect(self.page.get_by_role("button", name="Tạo báo cáo thị trường bằng Gemini")).to_have_count(0)
        self.page.get_by_role("button", name="Đặt lại bộ lọc").click()
        expect(self.page.locator("#market-sector")).to_have_value("industry")
        expect(self.page.locator("#market-min")).to_be_empty()
        self.assertEqual(self.page.locator("#market-countries").evaluate("el => el.selectedOptions.length"), 0)
        expect(self.page.locator(".market-results")).to_have_count(0)

    def test_all_sectors_clears_dependencies_and_report_works(self):
        self.manual()
        self.page.locator("#market-min").fill("30")
        self.page.locator("#market-sector").select_option("all")
        expect(self.page.locator("#market-min")).to_be_disabled()
        expect(self.page.locator("#market-min")).to_be_empty()
        expect(self.page.locator("#market-sort")).to_have_value("total_ghg")
        expect(self.page.locator('#market-sort option[value="sector_emissions"]')).to_have_attribute("disabled", "")
        self.search()
        query = [p for path, p in self.calls if path == "/market/search"][-1]
        self.assertIsNone(query["min_sector_share_percent"])
        self.assertEqual(query["sector"], "all")
        expect(self.page.locator(".market-table tbody tr").first.locator("td").nth(2)).to_have_text("—")
        self.page.get_by_role("button", name="Tạo báo cáo thị trường bằng Gemini").click()
        expect(self.page.locator(".ce-report")).to_be_visible()

    def test_mobile_and_desktop_layouts(self):
        for width in [1440, 768, 390, 320]:
            self.page.set_viewport_size({"width": width, "height": 900})
            self.manual()
            expect(self.page.locator("#market-sector")).to_be_visible()
            self.search()
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow at {width}px")
            expect(self.page.locator(".worldmap")).to_be_visible()
            if os.environ.get("MARKET_UI_SCREENSHOTS") and width in [1440, 390]:
                directory = Path(os.environ["MARKET_UI_SCREENSHOTS"])
                directory.mkdir(parents=True, exist_ok=True)
                self.page.locator(".market-mode-switch").scroll_into_view_if_needed()
                self.page.screenshot(path=str(directory / f"market-{width}.png"))
            self.page.locator('.market-mode-switch button').first.click()
            expect(self.page.locator("#market-request")).to_be_visible()
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"AI overflow at {width}px")


if __name__ == "__main__":
    unittest.main(verbosity=2)
