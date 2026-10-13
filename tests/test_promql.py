import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-server-metrics"))

from queries import CONTAINERS, MEMORY, limit_query, memory_query, predict_query


class PromqlTest(unittest.TestCase):
    def test_filters_drop_pod_cgroup_and_pause(self):
        self.assertIn('container!=""', CONTAINERS)
        self.assertIn('container!="POD"', CONTAINERS)
        self.assertEqual(MEMORY, "container_memory_working_set_bytes")

    def test_queries_name_the_pod_and_the_working_set(self):
        self.assertIn('pod="web-0"', memory_query("web-0"))
        self.assertIn(MEMORY, memory_query("web-0"))
        self.assertIn("container_spec_memory_limit_bytes", limit_query("web-0"))

    def test_forecast_uses_predict_linear(self):
        query = predict_query("web-0", 3600)
        self.assertTrue(query.startswith("predict_linear("))
        self.assertIn("3600", query)
        self.assertIn("[30m]", query)


if __name__ == "__main__":
    unittest.main()
