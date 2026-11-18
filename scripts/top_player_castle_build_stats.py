#!/usr/bin/env python3
"""Download/analyze public replays to derive castle-build thresholds."""

import argparse
import csv
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.generals.bot"
SCHEMA_VERSION = 2


def get_json(path):
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def safe_name(value):
    # Player names and API-provided match IDs must stay within the output directory.
    if not value or value in (".", "..") or any(c in value for c in "/\\\0:"):
        raise ValueError(f"unsafe filename component: {value!r}")
    return value


def selected_matches(player, max_replays):
    query = urllib.parse.urlencode({"matches": 1, "player": player})
    matches = get_json(f"/api/leaderboard?{query}")["matches"]
    selected = matches if max_replays is None else matches[:max_replays]
    for match in selected:
        safe_name(str(match["id"]))
    return selected


def download_selected(player, out, max_replays):
    out.mkdir(parents=True, exist_ok=True)
    matches = selected_matches(player, max_replays)
    failures = []
    cached = fetched = 0
    for m in matches:
        p = out / f"replay_{m['id']}.json"
        if p.exists():
            cached += 1
            continue
        try:
            p.write_text(json.dumps(get_json(m["replay"])))
            fetched += 1
            time.sleep(0.05)
        except Exception as e:  # fail closed at profile level
            failures.append({"id": m.get("id"), "error": str(e)})
    (out / "matches.json").write_text(json.dumps(matches, indent=2))
    return matches, {"selected": len(matches), "fetched": fetched, "cached": cached, "failed": len(failures), "failures": failures}


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def initial_castles(replay):
    out = set()
    for item in replay.get("castles") or replay.get("cities") or ():
        pos = item.get("pos") if isinstance(item, dict) else item
        out.add(tuple(pos))
    return out


def build_cost(structures, rc):
    cost = 35
    for s in structures:
        surcharge = 14 - 2 * dist(rc, s)
        if surcharge > 0:
            cost += surcharge
    return cost


def visible_enemy_cells(tick, player):
    owners = tick["owners"]
    h, w = len(owners), len(owners[0])
    visible = set()
    for r, row in enumerate(owners):
        for c, owner in enumerate(row):
            if owner == player:
                for rr in range(max(0, r - 1), min(h, r + 2)):
                    for cc in range(max(0, c - 1), min(w, c + 2)):
                        visible.add((rr, cc))
    return [(r, c) for r, c in visible if owners[r][c] == 1 - player]


def validate_replay(replay, player_name):
    if replay.get("version") != 1 or len(replay.get("players", [])) != 2:
        raise ValueError("unsupported replay schema")
    if player_name not in replay["players"]:
        raise ValueError(f"{player_name} absent from replay")
    if len(replay.get("generals", [])) != 2:
        raise ValueError("missing generals")


def analyze_replay(path, player_name, source="top_player"):
    replay = json.loads(path.read_text())
    validate_replay(replay, player_name)
    player = replay["players"].index(player_name)
    all_structures = initial_castles(replay) | {tuple(replay["generals"][0]), tuple(replay["generals"][1])}
    rows = []
    for result_turn, tick in enumerate(replay["ticks"]):
        for br, bc in tick.get("built", []):
            if result_turn <= 0:
                raise ValueError(f"build at tick 0 in {path}")
            pre = replay["ticks"][result_turn - 1]
            owner = pre["owners"][br][bc]
            if owner not in (0, 1):
                continue
            if owner == player:
                rc = (br, bc)
                owned_structures = {s for s in all_structures if pre["owners"][s[0]][s[1]] == player}
                prior_owned = owned_structures or {rc}
                enemy_cells = visible_enemy_cells(pre, player)
                rows.append({
                    "replay": path.stem.replace("replay_", ""),
                    "player": player_name,
                    "turn": result_turn - 1,
                    "row": br,
                    "col": bc,
                    "source": source,
                    "army_after": pre["armies"][br][bc] - build_cost(owned_structures, rc),
                    "structure_d": min(dist(rc, s) for s in prior_owned),
                    "enemy_d": min([dist(rc, e) for e in enemy_cells] or [999]),
                })
            all_structures.add((br, bc))
    return rows


def quantile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]


def dedupe(rows):
    merged = {}
    raw = len(rows)
    metric_fields = ("army_after", "structure_d", "enemy_d")
    for row in rows:
        key = (row["replay"], row["player"], row["turn"], row["row"], row["col"])
        if key not in merged:
            row = dict(row)
            row["source"] = row["source"]
            merged[key] = row
            continue
        old = merged[key]
        for field in metric_fields:
            if old[field] != row[field]:
                raise ValueError(f"duplicate metric mismatch for {key}: {field}")
        old["source"] = ";".join(sorted(set(old["source"].split(";")) | {row["source"]}))
    out = sorted(merged.values(), key=lambda r: (r["replay"], r["player"], r["turn"], r["row"], r["col"]))
    return out, raw, raw - len(out)


def require_finite_profile(profile):
    for k in ("turn_p10", "turn_p90", "army_after_p25", "enemy_d_p25", "structure_d_p25"):
        v = profile[k]
        if v is None or not math.isfinite(v):
            raise ValueError(f"non-finite {k}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--players", nargs="*", default=[])
    ap.add_argument("--opponents-of", nargs="*", default=[], help="mine top opponents in these players' matches")
    ap.add_argument("--opponent-top", type=int, default=15, help="current leaderboard rank cutoff")
    ap.add_argument("--out", default="data/top_player_castles")
    ap.add_argument("--max-replays", type=int, default=None, help="positive cap; omit for all returned matches")
    args = ap.parse_args()
    if not args.players and not args.opponents_of:
        ap.error("provide --players and/or --opponents-of")
    if args.opponent_top <= 0:
        ap.error("--opponent-top must be positive")
    if args.max_replays is not None and args.max_replays <= 0:
        ap.error("--max-replays must be positive when supplied")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for stale in (out / "castle_builds.csv", out / "castle_profile.json"):
        stale.unlink(missing_ok=True)

    rows = []
    manifests = {}
    queries = {}
    selected_top = []
    for player in args.players:
        pdir = out / safe_name(player)
        matches, stats = download_selected(player, pdir, args.max_replays)
        manifests[player] = sorted(m["id"] for m in matches)
        queries[player] = stats
        if stats["failed"]:
            raise SystemExit(f"failed selected downloads for {player}: {stats['failures']}")
        for m in matches:
            rows.extend(analyze_replay(pdir / f"replay_{m['id']}.json", player))

    if args.opponents_of:
        leaders = get_json("/api/leaderboard")["leaderboard"]
        selected_top = [{"rank": i + 1, "label": e["label"], "elo": e.get("elo")} for i, e in enumerate(leaders[:args.opponent_top])]
        top = {entry["label"] for entry in selected_top}
        for focal in args.opponents_of:
            pdir = out / ("opponents_of_" + safe_name(focal))
            matches, stats = download_selected(focal, pdir, args.max_replays)
            manifest_key = "opponents_of_" + focal
            manifests[manifest_key] = sorted(m["id"] for m in matches)
            queries[manifest_key] = stats
            if stats["failed"]:
                raise SystemExit(f"failed selected downloads for {focal}: {stats['failures']}")
            for m in matches:
                replay_path = pdir / f"replay_{m['id']}.json"
                replay = json.loads(replay_path.read_text())
                if focal not in replay.get("players", []):
                    raise SystemExit(f"{focal} absent from selected replay {m['id']}")
                for opponent in sorted((set(replay.get("players", [])) & top) - {focal}):
                    rows.extend(analyze_replay(replay_path, opponent, "top_opponent_vs_" + focal))

    rows, raw_count, duplicate_count = dedupe(rows)
    fieldnames = ["replay", "player", "turn", "row", "col", "source", "army_after", "structure_d", "enemy_d"]
    with (out / "castle_builds.csv.tmp").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)
    source_counts = Counter(source for r in rows for source in r["source"].split(";"))
    player_counts = Counter(r["player"] for r in rows)
    profile = {
        "schema_version": SCHEMA_VERSION,
        "quantile_method": "lower_index",
        "api_endpoint": BASE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_top": selected_top,
        "manifests": manifests,
        "queries": queries,
        "count": len(rows),
        "raw_provenance_count": raw_count,
        "duplicate_count": duplicate_count,
        "overlap_count": sum(";" in r["source"] for r in rows),
        "source_counts": dict(sorted(source_counts.items())),
        "player_counts": dict(sorted(player_counts.items())),
        "turn_p10": quantile([r["turn"] for r in rows], 0.10),
        "turn_p90": quantile([r["turn"] for r in rows], 0.90),
        "army_after_p25": quantile([r["army_after"] for r in rows], 0.25),
        "enemy_d_p25": quantile([r["enemy_d"] for r in rows if r["enemy_d"] < 999], 0.25),
        "structure_d_p25": quantile([r["structure_d"] for r in rows], 0.25),
    }
    require_finite_profile(profile)
    (out / "castle_profile.json.tmp").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")
    (out / "castle_builds.csv.tmp").replace(out / "castle_builds.csv")
    (out / "castle_profile.json.tmp").replace(out / "castle_profile.json")
    print(json.dumps(profile, indent=2, sort_keys=True))
    if rows:
        print(f"median turn={statistics.median(r['turn'] for r in rows):.0f} army_after={statistics.median(r['army_after'] for r in rows):.0f}")


if __name__ == "__main__":
    main()
