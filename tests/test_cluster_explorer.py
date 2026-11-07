"""Run: python -m unittest discover -s tests -v. Never calls Gemini."""
import csv
import io
import json
import math
import statistics
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import advisor_service as advisor, data_service as data
from api.main import app


class ClusterExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.stats = data.cluster_explorer()
        with data.CITY_PATH.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_all_three_clusters_against_source(self):
        self.assertEqual(self.stats["total_cities"], 11422)
        self.assertEqual([c["city_count"] for c in self.stats["clusters"]], [7480, 3177, 765])
        self.assertAlmostEqual(sum(c["city_percentage"] for c in self.stats["clusters"]), 100)
        for cluster in self.stats["clusters"]:
            with self.subTest(cluster=cluster["cluster_id"]):
                rows = [r for r in self.rows if int(r["cluster_id"]) == cluster["cluster_id"]]
                self.assertEqual(len(rows), cluster["city_count"])
                self.assertAlmostEqual(sum(cluster["centroid_percent"].values()), 100)
                for sector in data.SECTORS:
                    values = sorted(float(r[f"share_{sector}_2024"]) * 100 for r in rows)
                    stats = cluster["sector_statistics_percent"][sector]
                    self.assertAlmostEqual(stats["mean"], sum(values) / len(values))
                    self.assertAlmostEqual(stats["median"], statistics.median(values))
                    variance = sum((x - stats["mean"]) ** 2 for x in values) / len(values)
                    self.assertAlmostEqual(stats["std"], math.sqrt(variance))
                    quartiles = statistics.quantiles(values, n=4, method="inclusive")
                    self.assertAlmostEqual(stats["q1"], quartiles[0])
                    self.assertAlmostEqual(stats["q3"], quartiles[2])
                    self.assertAlmostEqual(stats["iqr"], quartiles[2] - quartiles[0])
                distances = []
                center = [cluster["centroid_percent"][s] / 100 for s in data.SECTORS]
                for row in rows:
                    distance = math.sqrt(sum((float(row[f"share_{s}_2024"]) - center[i]) ** 2 for i, s in enumerate(data.SECTORS)))
                    self.assertAlmostEqual(distance, float(row["distance_to_centroid"]), places=10)
                    distances.append(distance)
                dist = cluster["distance_statistics"]
                self.assertAlmostEqual(dist["mean"], statistics.mean(distances))
                self.assertAlmostEqual(dist["median"], statistics.median(distances))
                self.assertAlmostEqual(dist["std"], statistics.pstdev(distances))
                ordered = sorted(distances)
                for key, p in [("q1", .25), ("q3", .75), ("p90", .9), ("p95", .95)]:
                    position = (len(ordered) - 1) * p
                    expected = ordered[math.floor(position)] * (1 - position % 1) + ordered[math.ceil(position)] * (position % 1)
                    self.assertAlmostEqual(dist[key], expected)
                for other in self.stats["clusters"]:
                    if other is cluster:
                        continue
                    for s in data.SECTORS:
                        self.assertAlmostEqual(cluster["comparison_percentage_points"][str(other["cluster_id"])][s], cluster["mean_sector_shares_percent"][s] - other["mean_sector_shares_percent"][s])

    def test_endpoints_and_existing_pages_data(self):
        for route in ["/api/health", "/api/meta", "/api/overview", "/api/clusters", "/api/countries", "/api/cities", "/api/cities/map", "/api/cities/1", "/api/catalog", "/api/cluster-explorer"]:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(self.client.get("/api/overview").json()["total_cities"], 11422)
        for cid in range(3):
            response = self.client.get(f"/api/cluster-explorer/{cid}/preview")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["selected_cluster_id"], cid)
            self.assertEqual(len(response.json()["clusters"]), 3)
        for cid in [-1, 3, "abc"]:
            self.assertEqual(self.client.get(f"/api/cluster-explorer/{cid}/preview").status_code, 422)
            self.assertEqual(self.client.post(f"/api/cluster-explorer/{cid}/interpret", json={}).status_code, 422)
        self.assertEqual(self.client.get("/api/cities/missing").status_code, 404)

    def test_gemini_schema_and_context_without_network(self):
        answer = {"summary": "Tóm tắt kiểm thử", "comparisons": ["So sánh thứ nhất", "So sánh thứ hai"],
                  "dispersion_and_representativeness": "Diễn giải kiểm thử", "research_questions": ["Cần nghiên cứu thêm"], "limitations": ["Giới hạn kiểm thử"]}
        with patch.object(advisor._advisor(), "call_gemini", return_value=answer) as call:
            for cid in range(3):
                response = self.client.post(f"/api/cluster-explorer/{cid}/interpret", json={})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["cluster_id"], cid)
                self.assertEqual(response.json()["report"], answer)
                context = call.call_args.args[0]
                self.assertEqual(context["selected_cluster_id"], cid)
                self.assertEqual(context["clusters"], self.stats["clusters"])
                self.assertNotIn("catalog_solutions", context)
                self.assertEqual(call.call_args.kwargs["response_schema"]["required"], list(answer))

    def test_malformed_and_provider_errors_are_safe(self):
        for output in [{}, {"summary": 123}, {"summary": ""}]:
            with patch.object(advisor._advisor(), "call_gemini", return_value=output):
                self.assertEqual(self.client.post("/api/cluster-explorer/0/interpret", json={}).status_code, 503)
        for message in ["Chưa đặt GEMINI_API_KEY", "HTTP 503 secret-provider-body"]:
            with patch.object(advisor._advisor(), "call_gemini", side_effect=RuntimeError(message)):
                response = self.client.post("/api/cluster-explorer/0/interpret", json={})
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret-provider-body", response.text)

    def test_existing_advisor_preview_works_without_gemini(self):
        with patch.object(advisor._advisor(), "call_gemini", side_effect=AssertionError("Network forbidden")):
            for payload in [{"mode": "city", "city_id": "1"}, {"mode": "cluster", "cluster_id": 0}]:
                self.assertEqual(self.client.post("/api/advisor/preview", json=payload).status_code, 200)

    def test_transport_preserves_existing_advisor_defaults(self):
        module = advisor._advisor()
        response = json.dumps({"candidates": [{"content": {"parts": [{"text": '{"result":"ok"}'}]}}]}).encode()
        with patch.dict(module.os.environ, {"GEMINI_API_KEY": "unit-test-key"}):
            with patch.object(module, "urlopen", return_value=io.BytesIO(response)) as transport:
                module.call_gemini({}, module.DEFAULT_MODEL)
                body = json.loads(transport.call_args.args[0].data)
                self.assertEqual(body["generationConfig"]["responseJsonSchema"], module.RESPONSE_SCHEMA)
                self.assertTrue(body["contents"][0]["parts"][0]["text"].startswith(module.SYSTEM_RULES))
            with patch.object(module, "urlopen", return_value=io.BytesIO(response)) as transport:
                schema = advisor.ClusterInterpretation.model_json_schema()
                module.call_gemini({}, module.DEFAULT_MODEL, system_rules=advisor.CLUSTER_RULES, response_schema=schema)
                body = json.loads(transport.call_args.args[0].data)
                self.assertEqual(body["generationConfig"]["responseJsonSchema"], schema)
                self.assertTrue(body["contents"][0]["parts"][0]["text"].startswith(advisor.CLUSTER_RULES))

    def test_corrupt_distance_rejected(self):
        original = data._read_csv
        def corrupted(path):
            rows = original(path)
            if path == data.CITY_PATH:
                rows[0]["distance_to_centroid"] = "nan"
            return rows
        data.cluster_explorer.cache_clear()
        try:
            with patch.object(data, "_read_csv", side_effect=corrupted):
                with self.assertRaisesRegex(ValueError, "Khoảng cách"):
                    data.cluster_explorer()
        finally:
            data.cluster_explorer.cache_clear()


if __name__ == "__main__":
    unittest.main()
