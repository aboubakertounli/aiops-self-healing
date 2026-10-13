import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-server-infra"))

from policy import cooldown_remaining, namespace_allowed, parse_allowlist


class RestartPolicyTest(unittest.TestCase):
    def test_kube_system_is_always_refused(self):
        self.assertFalse(namespace_allowed("kube-system", set()))
        self.assertFalse(namespace_allowed("kube-system", {"kube-system"}))

    def test_empty_allowlist_permits_application_namespaces(self):
        self.assertTrue(namespace_allowed("default", set()))
        self.assertTrue(namespace_allowed("train-ticket", set()))

    def test_allowlist_limits_restarts(self):
        allow = parse_allowlist("default, demo")
        self.assertEqual(allow, {"default", "demo"})
        self.assertTrue(namespace_allowed("demo", allow))
        self.assertFalse(namespace_allowed("other", allow))

    def test_cooldown_counts_remaining_seconds(self):
        self.assertEqual(cooldown_remaining(None, 1000, 300), 0)
        self.assertEqual(cooldown_remaining(800, 1000, 300), 100)
        self.assertEqual(cooldown_remaining(800, 1200, 300), 0)


if __name__ == "__main__":
    unittest.main()
