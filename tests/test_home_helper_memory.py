import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HomeHelperMemoryTests(unittest.TestCase):
    def test_home_helper_is_the_only_active_memory_contract(self) -> None:
        mode = json.loads((ROOT / "memory/modes/home_helper.json").read_text())
        identity = json.loads((ROOT / "memory/identity.json").read_text())

        self.assertEqual(mode["mode_name"], "home_helper")
        self.assertEqual(mode["knowledge_files"], [
            "home_helper_overview.txt",
            "sensor_guidance.txt",
            "safety_boundaries.txt",
        ])
        self.assertEqual(identity["type"], "local-first home helper")
        self.assertEqual(
            sorted(path.name for path in (ROOT / "memory/modes").iterdir()),
            ["home_helper.json"],
        )
        self.assertEqual(
            sorted(path.name for path in (ROOT / "memory/knowledge").iterdir()),
            [
                "home_helper_overview.txt",
                "safety_boundaries.txt",
                "sensor_guidance.txt",
            ],
        )
        self.assertFalse((ROOT / "memory/active_mode.txt").exists())


if __name__ == "__main__":
    unittest.main()
