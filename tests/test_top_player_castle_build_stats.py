import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import top_player_castle_build_stats as stats


def replay(players=("builder", "capturer"), build=(2, 4)):
    owners = [[-1] * 5 for _ in range(5)]
    armies = [[0] * 5 for _ in range(5)]
    for r, c in [(0, 0), (0, 1), (2, 2), (2, 3), build]:
        owners[r][c] = 0
    owners[4][4] = 1
    owners[3][3] = 1
    armies[build[0]][build[1]] = 60
    pre = {"owners": owners, "armies": armies}
    post_owners = [row[:] for row in owners]
    post_armies = [row[:] for row in armies]
    post_owners[build[0]][build[1]] = 1
    post = {"owners": post_owners, "armies": post_armies, "built": [list(build)]}
    return {
        "version": 1,
        "players": list(players),
        "generals": [[0, 0], [4, 4]],
        "castles": [{"pos": [2, 2]}],
        "ticks": [pre, post],
    }


class TopPlayerCastleBuildStatsTest(unittest.TestCase):
    def test_filename_components_cannot_escape_output_directory(self):
        self.assertEqual(stats.safe_name("player-1"), "player-1")
        for value in ("", ".", "..", "../outside", "dir/file", "dir\\file", "C:outside", "null\0name"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                stats.safe_name(value)

    def test_remote_match_ids_are_validated_before_download(self):
        matches = [{"id": "../../outside", "replay": "/replays/unsafe"}]
        with patch.object(stats, "get_json", return_value={"matches": matches}), \
             tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                stats.download_selected("builder", Path(directory), 1)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_decision_state_builder_cost_distance_and_visible_enemy(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "replay_r1.json"
            path.write_text(json.dumps(replay()))
            rows = stats.analyze_replay(path, "builder")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["turn"], 0)
        self.assertEqual(row["player"], "builder")
        self.assertEqual(row["army_after"], 13)  # 60 - (35 + 10 near castle + 2 near general)
        self.assertEqual(row["structure_d"], 2)
        self.assertEqual(row["enemy_d"], 2)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "replay_r1.json"
            path.write_text(json.dumps(replay()))
            self.assertEqual(stats.analyze_replay(path, "capturer"), [])

    def test_overlap_provenance_unions_sources_deterministically(self):
        row = {
            "replay": "r1", "player": "builder", "turn": 0, "row": 2, "col": 4,
            "source": "top_player", "army_after": 13, "structure_d": 2, "enemy_d": 2,
        }
        other = dict(row, source="top_opponent_vs_focus")
        rows, raw, dupes = stats.dedupe([other, row])
        self.assertEqual(raw, 2)
        self.assertEqual(dupes, 1)
        self.assertEqual(rows[0]["source"], "top_opponent_vs_focus;top_player")

    def test_main_ignores_stale_replays_outside_manifest(self):
        selected = replay(build=(2, 4))
        stale = replay(build=(1, 1))
        def fake_get_json(path):
            if path.startswith("/api/leaderboard?"):
                return {"matches": [{"id": "selected", "replay": "/replays/selected"}]}
            if path == "/replays/selected":
                return selected
            raise AssertionError(path)

        with tempfile.TemporaryDirectory() as td, patch.object(stats, "get_json", side_effect=fake_get_json), patch.object(stats.time, "sleep"):
            out = Path(td)
            pdir = out / "builder"
            pdir.mkdir()
            (pdir / "replay_stale.json").write_text(json.dumps(stale))
            argv = ["prog", "--players", "builder", "--max-replays", "1", "--out", str(out)]
            with patch.object(sys, "argv", argv):
                stats.main()
            with (out / "castle_builds.csv").open() as f:
                rows = list(csv.DictReader(f))
            profile = json.loads((out / "castle_profile.json").read_text())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["replay"], "selected")
        self.assertEqual(profile["count"], 1)
        self.assertEqual(profile["player_counts"], {"builder": 1})
        self.assertEqual(profile["source_counts"], {"top_player": 1})
        self.assertEqual(profile["raw_provenance_count"], 1)
        self.assertEqual(profile["duplicate_count"], 0)
        self.assertEqual(profile["manifests"], {"builder": ["selected"]})


if __name__ == "__main__":
    unittest.main()
