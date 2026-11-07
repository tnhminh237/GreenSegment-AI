"""Report-only diagnosis through the real transport with mocked urllib; no Gemini traffic."""
import io
import json
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient

from api import advisor_service as advisor, market_service as market
from api.main import app
import test_market_explorer as fixtures


class MarketReportDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.request = market.ReportRequest(query=market.MarketQuery(
            sector="industry", countries=["Japan"], min_sector_share_percent=30),
            business_request="PRIVATE_BUSINESS_REQUEST")
        cls.context = market.report_context(cls.request)
        cls.module = advisor._advisor()

    def api(self):
        return self.client.post("/api/market/report", json=self.request.model_dump())

    def assert_private(self, response, logs):
        combined = response.text + "\n".join(logs.output)
        for secret in ["SECRET_API_KEY", "PRIVATE_BUSINESS_REQUEST", "PRIVATE_RESPONSE_BODY", "PRIVATE_BAD_FIELD", "Authorization"]:
            self.assertNotIn(secret, combined)
        self.assertEqual(response.headers["X-Request-ID"], response.json()["request_id"])
        self.assertIn(response.json()["request_id"], "\n".join(logs.output))

    def test_actual_transport_http_statuses_are_separate_and_redacted(self):
        for upstream, expected in [(429, 429), (500, 502), (502, 502), (503, 503)]:
            with self.subTest(status=upstream), \
                    patch.dict(self.module.os.environ, {"GEMINI_API_KEY": "SECRET_API_KEY"}), \
                    patch.object(self.module, "urlopen", side_effect=HTTPError(
                        "https://provider.invalid/?api_key=SECRET_API_KEY", upstream, "Authorization PRIVATE_RESPONSE_BODY", {}, io.BytesIO(b"PRIVATE_RESPONSE_BODY"))) as transport, \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
                response = self.api()
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.json()["error_code"], "gemini_http")
                self.assertEqual(response.json()["provider_status"], upstream)
                self.assertEqual(transport.call_count, 1)  # No content repair or hidden HTTP retries.
                self.assertIn('"cause_type": "HTTPError"', "\n".join(logs.output))
                self.assert_private(response, logs)

    def test_actual_transport_connection_timeout_and_json_errors(self):
        cases = [(URLError("PRIVATE_RESPONSE_BODY"), "gemini_connection", 503),
                 (TimeoutError("SECRET_API_KEY"), "gemini_timeout", 504),
                 (URLError(socket.timeout("PRIVATE_RESPONSE_BODY")), "gemini_timeout", 504)]
        for error, code, status in cases:
            with self.subTest(code=code), \
                    patch.dict(self.module.os.environ, {"GEMINI_API_KEY": "SECRET_API_KEY"}), \
                    patch.object(self.module, "urlopen", side_effect=error) as transport, \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
                response = self.api()
                self.assertEqual((response.status_code, response.json()["error_code"]), (status, code))
                self.assertEqual(transport.call_count, 1)
                self.assert_private(response, logs)
        envelopes = [b"PRIVATE_RESPONSE_BODY is not json", json.dumps({"candidates": [{"content": {"parts": [{"text": "PRIVATE_RESPONSE_BODY is not json"}]}}]}).encode()]
        for body in envelopes:
            with patch.dict(self.module.os.environ, {"GEMINI_API_KEY": "SECRET_API_KEY"}), \
                    patch.object(self.module, "urlopen", return_value=io.BytesIO(body)), \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
                response = self.api()
                self.assertEqual((response.status_code, response.json()["error_code"]), (502, "gemini_json"))
                self.assertIn('"json_line"', "\n".join(logs.output))
                self.assert_private(response, logs)

    def test_missing_key_is_configuration_without_network(self):
        with patch.dict(self.module.os.environ, {"GEMINI_API_KEY": ""}), \
                patch.object(self.module, "urlopen", side_effect=AssertionError("No network without key")) as transport, \
                self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
            response = self.api()
            self.assertEqual((response.status_code, response.json()["error_code"]), (503, "gemini_config"))
            transport.assert_not_called()
            self.assert_private(response, logs)

    def test_transport_valid_json_city_cluster_and_spaced_fact_references_succeeds(self):
        report = fixtures.MarketExplorerTests.report_fixture(self.context)
        city = self.context["representative_cities"][0]
        prefix = "cities." + city["city_id"]
        report["emissions_profile"] = city["city_name"] + " thuộc Cụm {{ " + prefix + ".cluster_id }}, có tỷ trọng Công nghiệp {{ verified_facts." + prefix + ".sector_share_percent.display }}."
        envelope = json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(report, ensure_ascii=False)}]}}]}).encode()
        with patch.dict(self.module.os.environ, {"GEMINI_API_KEY": "SECRET_API_KEY"}), \
                patch.object(self.module, "urlopen", side_effect=lambda *args, **kwargs: io.BytesIO(envelope)) as transport, \
                self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
            response = self.api()
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(response.json()["diagnostics"]["validator_version"], "verified-facts-v2")
            self.assertIn(self.context["verified_facts"][prefix + ".sector_share_percent"]["display"], response.json()["report"]["emissions_profile"])
            self.assertNotIn("{{", response.json()["report"]["emissions_profile"])
            for secret in ["SECRET_API_KEY", "PRIVATE_BUSINESS_REQUEST", report["emissions_profile"]]:
                self.assertNotIn(secret, "\n".join(logs.output))

    def test_rounded_percentage_false_positive_and_ordinals_are_fixed(self):
        # Real mean is 47.06; the old exact-membership guard rejected these valid displays.
        self.assertEqual(self.context["matching_summary"]["mean_sector_share_percent"], 47.06)
        for text in ["Tỷ trọng trung bình 47,1%", "Tỷ trọng trung bình 47%", "1. a; 2. b; 3. c; 4. d; 5. e."]:
            market.render_verified_text(text, "emissions_profile", self.context)
        for text in ["Có 41 đô thị.", "Có 5 đô thị.", "Tỷ trọng 99,99%."]:
            with self.assertRaises(market.FactValidationError):
                market.render_verified_text(text, "emissions_profile", self.context)
        answer = fixtures.MarketExplorerTests.report_fixture(self.context)
        answer["emissions_profile"] += " Tỷ trọng trung bình khoảng 47,1%."
        with patch.object(self.module, "call_gemini", return_value=answer) as call, \
                self.assertLogs(market.REPORT_LOG.name, level="INFO"):
            response = self.api()
            self.assertEqual(response.status_code, 200)
            self.assertIn("47,06%", response.json()["report"]["emissions_profile"])
            self.assertNotIn("47,10%", response.json()["report"]["emissions_profile"])
            self.assertEqual(call.call_count, 1)
            self.assertFalse(response.json()["diagnostics"]["correction_attempted"])
        self.assertEqual(self.context["matching_summary"]["cluster_percentages"], {"0": 22.5, "1": 55.0, "2": 22.5})

    def test_invalid_schema_gets_one_checked_repair_and_logs_both_counts(self):
        valid = fixtures.MarketExplorerTests.report_fixture(self.context)
        empty = {**valid, "limitations": "   "}
        for invalid in [{"PRIVATE_BAD_FIELD": "PRIVATE_RESPONSE_BODY"}, empty]:
            with self.subTest(invalid_fields=list(invalid)), patch.object(self.module, "call_gemini", side_effect=[invalid, valid]) as call, \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
                response = self.api()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(call.call_count, 2)
                self.assertTrue(response.json()["diagnostics"]["correction_attempted"])
                second = call.call_args_list[1].args[0]
                self.assertEqual(second["correction"]["category"], "report_schema")
                self.assertEqual(second["matching_summary"], self.context["matching_summary"])
                counts = response.json()["diagnostics"]["attempt_word_counts"]
                self.assertEqual([c["raw_word_count"] for c in counts], [market._report_word_count(invalid), market._report_word_count(valid)])
                for attempt in (1, 2):
                    self.assertIn(f'"attempt": {attempt}, "raw_word_count":', "\n".join(logs.output))
                self.assertNotIn("PRIVATE_BAD_FIELD", "\n".join(logs.output))
                self.assertNotIn("PRIVATE_RESPONSE_BODY", "\n".join(logs.output))
        with patch.object(self.module, "call_gemini", return_value=empty) as call, \
                self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
            response = self.api()
            self.assertEqual((response.status_code, response.json()["error_code"]), (502, "report_schema"))
            self.assertEqual(call.call_count, 2)
            self.assert_private(response, logs)

    def short_report(self):
        return {
            "research_request": "Bộ lọc đã xác nhận dùng để sàng lọc đô thị theo phát thải Công nghiệp tại Nhật Bản, không phải tìm khách hàng đã có nhu cầu mua.",
            "emissions_profile": "Tỷ trọng thể hiện cơ cấu tương đối; GHG tuyệt đối giữ đơn vị gốc EDGAR chưa xác minh. Không thể suy ra loại thiết bị từ hai chỉ số này.",
            "cluster_distribution": "Các cụm mô tả cấu trúc phát thải. Chúng không chứng minh các đô thị có cùng hạ tầng hoặc điều kiện thương mại.",
            "city_comparisons": [{"city_id": self.context["representative_cities"][0]["city_id"], "text": "Đô thị được chọn minh họa từ Top N theo thứ tự đã xác nhận. Vị trí này không phải điểm tiềm năng thị trường."}],
            "preliminary_technology_link": "Quan hệ giữa công nghệ và lĩnh vực phát thải chỉ là giả thuyết cần kiểm chứng bằng dữ liệu vận hành tại cơ sở cụ thể.",
            "additional_information": ["Cần xác minh hạ tầng và ngành hoạt động thực tế.", "Cần bổ sung chính sách, ngân sách và đơn vị mua sắm.", "Cần khảo sát nhu cầu thực tế trước khi tiếp cận thị trường."],
            "limitations": "Dữ liệu năm 2024 và K=3 không dự báo doanh số, nguyên nhân phát thải hay khả năng triển khai công nghệ. Không khẳng định có nhu cầu mua."}

    def long_report(self):
        report = fixtures.MarketExplorerTests.report_fixture(self.context)
        report["additional_information"] += [
            "Đối với hạ tầng, cần xác định phạm vi cơ sở được khảo sát, điều kiện vận hành và mức độ phù hợp của nguồn thông tin. Những nội dung này là việc cần nghiên cứu thêm, không phải dữ kiện đã có trong EDGAR.",
            "Đối với tiếp cận thị trường, cần làm rõ đơn vị nào có quyền quyết định mua sắm, cách phân bổ ngân sách và quy trình xác nhận nhu cầu. Danh sách đô thị không cung cấp các câu trả lời đó.",
            "Khi đối chiếu các đô thị, cần kiểm tra dữ liệu có cùng phạm vi và thời điểm hay không. Nếu nghiên cứu xu hướng, phải bổ sung dữ liệu ngoài năm 2024 trước khi đưa ra nhận định về thay đổi theo thời gian."]
        return report

    def test_valid_reports_outside_word_target_are_returned_without_second_call(self):
        for label, report in [("short", self.short_report()), ("long", self.long_report())]:
            with self.subTest(report=label), patch.object(self.module, "call_gemini", side_effect=[report, AssertionError("Must not call again for word count")]) as call, \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
                words = market._report_word_count(report)
                self.assertTrue(words < 300 if label == "short" else words > 450)
                response = self.api()
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(call.call_count, 1)
                self.assertEqual(response.json()["report"], report)
                diagnostics = response.json()["diagnostics"]
                self.assertEqual(diagnostics["word_count"], words)
                self.assertFalse(diagnostics["within_word_target"])
                self.assertFalse(diagnostics["correction_attempted"])
                self.assertFalse(diagnostics["word_target"]["required"])
                self.assertEqual(diagnostics["attempt_word_counts"], [{"attempt": 1, "raw_word_count": words, "normalized_word_count": words}])
                self.assertIn(f'"raw_word_count": {words}', "\n".join(logs.output))
                self.assertNotIn(report["research_request"], "\n".join(logs.output))

    def test_short_corrected_report_is_accepted_but_bad_data_still_rejected(self):
        short = self.short_report()
        with patch.object(self.module, "call_gemini", side_effect=[{}, short]) as call, \
                self.assertLogs(market.REPORT_LOG.name, level="INFO"):
            response = self.api()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(call.call_count, 2)
            self.assertEqual([c["raw_word_count"] for c in response.json()["diagnostics"]["attempt_word_counts"]], [0, market._report_word_count(short)])
        for report in [self.short_report(), self.long_report()]:
            report["emissions_profile"] += " Có 999999 khách hàng cam kết mua."
            with patch.object(self.module, "call_gemini", return_value=report) as call, \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO"):
                response = self.api()
                self.assertEqual((response.status_code, response.json()["error_code"]), (502, "report_numbers"))
                self.assertEqual(call.call_count, 2)

    def test_word_count_uses_only_prose_and_whitespace(self):
        report = {"research_request": "Tóm\ttắt\nphạm vi", "city_comparisons": [{"city_id": "5213 excluded", "text": "Nội dung đô thị."}],
                  "additional_information": ["Hạ tầng", "Ngân sách"], "unknown": "PRIVATE_RESPONSE_BODY is excluded"}
        self.assertEqual(market._report_word_count(report), 12)
        self.assertIsNone(market._report_word_count([]))

    def test_second_attempt_is_not_allowed_to_launder_unknown_numbers(self):
        invalid = fixtures.MarketExplorerTests.report_fixture(self.context)
        invalid["emissions_profile"] += " Có 999999 khách hàng."
        with patch.object(self.module, "call_gemini", return_value=invalid) as call, \
                self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
            response = self.api()
            self.assertEqual((response.status_code, response.json()["error_code"]), (502, "report_numbers"))
            self.assertEqual(call.call_count, 2)
            self.assertIn('"observed": "999999"', "\n".join(logs.output))
            self.assertIn('"field_path": "emissions_profile"', "\n".join(logs.output))
            self.assertNotIn(invalid["emissions_profile"], "\n".join(logs.output))

    def test_unexpected_python_errors_are_internal_not_provider_unavailability(self):
        for target in ["report_context", "_validate_report"]:
            with self.subTest(stage=target), patch.object(market, target, side_effect=TypeError("PRIVATE_RESPONSE_BODY")), \
                    patch.object(self.module, "call_gemini", return_value=fixtures.MarketExplorerTests.report_fixture(self.context)), \
                    self.assertLogs(market.REPORT_LOG.name, level="INFO") as logs:
                response = self.api()
                self.assertEqual((response.status_code, response.json()["error_code"]), (500, "report_internal"))
                self.assertIn('"exception_type": "TypeError"', "\n".join(logs.output))
                self.assert_private(response, logs)


if __name__ == "__main__":
    unittest.main()
