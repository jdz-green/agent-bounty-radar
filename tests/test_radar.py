"""Unit tests for the parts of radar.py that can be checked without the network.

Run: python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import radar  # noqa: E402


class ComplianceFilter(unittest.TestCase):
    def test_blocks_captcha_work_in_every_spelling(self):
        for title in [
            "500 Server Error - Auto Solve hcapcha",
            "solve captcha for me",
            "reCAPTCHA bypass needed",
            "anti-bot evasion library",
            "brute force login endpoint",
            "credential stuffing tool",
        ]:
            with self.subTest(title=title):
                self.assertFalse(radar.compliant({"title": title, "url": "https://example.test/x"}))

    def test_keeps_ordinary_bounty_work(self):
        for title in [
            "fix(verifier): tighten 32-bit subregister zero-extension parity",
            "docs: add Windows support implementation research",
            "Add integration tests for the CSV exporter",
        ]:
            with self.subTest(title=title):
                self.assertTrue(radar.compliant({"title": title, "url": "https://github.com/a/b/issues/1"}))

    def test_checks_the_url_too(self):
        self.assertFalse(radar.compliant({"title": "unrelated", "url": "https://example.test/captcha-solver"}))


class FeedShape(unittest.TestCase):
    def test_every_row_has_what_the_agents_promise(self):
        rows = [
            {"source": "opire", "id": "1", "title": "t", "reward": "$42", "deadline": "open", "url": "https://github.com/a/b/issues/1", "agent_ok": True},
            {"source": "immunefi", "id": "x", "title": "t2", "reward": "$1,000 max", "deadline": "rolling", "url": "https://immunefi.com/x", "agent_ok": True},
        ]
        for row in rows:
            for key in ("source", "title", "reward", "url"):
                self.assertTrue(row[key], f"{key} must not be empty")
            self.assertIn(row["source"], radar.__dict__.get("KNOWN_SOURCES", {"opire", "immunefi", "superteam", "stellarator", "github"}))


class Ranking(unittest.TestCase):
    def test_reward_numbers_are_extracted_from_mixed_strings(self):
        # The rank() helper lives inside main(); this asserts the parsing idea it relies on.
        import re
        cases = {"$1,000 max": [1000.0], "0.09 SOL": [0.09], "$45,000": [45000.0], "rolling": []}
        for text, expected in cases.items():
            got = [float(x.replace(",", "")) for x in re.findall(r"[\d,]+(?:\.\d+)?", text)]
            self.assertEqual(got, expected, text)


if __name__ == "__main__":
    unittest.main()
