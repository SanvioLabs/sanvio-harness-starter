"""Run with: python3 -m unittest discover -s tests"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def unreachable(settings):
    """Every enabled plugin whose marketplace the settings don't name. A fresh clone can't install those."""
    known = set(settings.get("extraKnownMarketplaces", {}))
    return sorted(plugin for plugin, on in settings.get("enabledPlugins", {}).items()
                  if on and plugin.partition("@")[2] not in known)


class Plugins(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / ".claude" / "settings.json").read_text())

    def test_every_enabled_plugin_comes_from_a_marketplace_the_repo_names(self):
        self.assertEqual(unreachable(self.settings), [])

    def test_a_plugin_from_an_unnamed_marketplace_is_caught(self):
        settings = {"extraKnownMarketplaces": {"stelliad": {}},
                    "enabledPlugins": {"stelliad@stelliad": True, "sanvio-studio@sanviolabs": True}}
        self.assertEqual(unreachable(settings), ["sanvio-studio@sanviolabs"])

    def test_stelliad_comes_from_its_public_repo(self):
        # Not whether it's on: switching it off in settings.json is a documented choice.
        source = self.settings["extraKnownMarketplaces"]["stelliad"]["source"]
        self.assertEqual(source, {"source": "github", "repo": "Stelliad/stelliad-skills"})

    def test_the_lens_counts_stelliad_skills_as_harness_skills(self):
        lens = json.loads((ROOT / ".claude" / "harness-lens.json").read_text())
        self.assertIn("stelliad:", lens["skillPrefixes"])


if __name__ == "__main__":
    unittest.main()
