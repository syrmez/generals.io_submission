# generals.io submission — engineering portfolio

** Python · replay analysis · reinforcement-learning systems**

A project write-up and standalone replay-analysis tool from my work on a generals.bot competition agent. The broader project progressed from a CPU-only heuristic to a roughly **7.1M-parameter transformer policy** with PPO runs using **256 vectorized environments** and 512-step rollouts.

**This public repository is a curated excerpt, not a runnable neural-agent submission.** It contains the replay analyzer and synthetic-data tests, not the AverageJoe-derived training/deployment code, simulator, weights, or competition archives. Those broader experiments are described below, not reproduced by this checkout.

## What you can run here

The [castle-build analyzer](scripts/top_player_castle_build_stats.py) reconstructs construction decisions from competition replays:

- Uses the **pre-action board state** to attribute a build to the correct player, even if the tile is captured in the resulting frame.
- Computes construction cost, remaining army, distance to owned structures, and distance to enemies visible from owned territory.
- Deduplicates replay events while retaining their source provenance; conflicting duplicate metrics are rejected.
- Analyzes only the selected replay manifest, not stale files left in a cache.
- Rejects incomplete/non-finite profiles and unsafe player-name or replay-ID path components.

### Run the tests offline

Python 3.12 was used for validation. The tool and tests use **only the standard library**; no GPU, weights, API credentials, or package installation is required.

```bash
git clone https://github.com/syrmez/generals.io_submission.git
cd generals.io_submission
python3 -m unittest discover -s tests -v
```

All test replays are synthetic and all HTTP calls in the tests are mocked. Tests cover decision-state attribution, build-cost arithmetic, visible-enemy distance, source deduplication, stale-cache exclusion, and path validation.

### Optional live replay collection

```bash
python3 scripts/top_player_castle_build_stats.py --help
python3 scripts/top_player_castle_build_stats.py \
  --players PLAYER_NAME --max-replays 10 --out data/castles
```

Replace `PLAYER_NAME` with a real competition player. This command contacts `https://www.generals.bot` and writes replay JSON, `castle_builds.csv`, and `castle_profile.json`. It relies on the historical competition API and schema-v1 replays; current endpoint availability and compatibility are **not verified**. Respect the service's access rules. Use a dedicated output directory: each run replaces its previous aggregate profile, and no successful profile is produced if downloads or required metrics are incomplete.

Cached replays and outputs stay in the ignored `data/` directory. No real player replays are distributed here. Enemy-distance summaries exclude the sentinel value `999`, which denotes no visible enemy; a dataset with no finite enemy-distance samples is rejected rather than presented as a valid profile.

## Broader project: engineering decisions

The full local project extended the [AverageJoe](https://github.com/strakam/AverageJoe) PPO/transformer framework and the [generals-bots](https://github.com/strakam/generals-bots) simulator. I did **not** write their original simulator or training framework, and their published superhuman results are not results of my project.

### 1. Start with a cheap baseline

I began with a no-GPU heuristic and small CPU training runs before moving to a compact transformer. This made it possible to separate pipeline failures from policy quality without trying to match the original paper's compute budget. The 256 environments were vectorized simulation, not a multi-machine distributed system.

### 2. Diagnose the missing behavior

Replay inspection exposed poor general defense, movement loops, and infrequent castle construction. Instead of assuming more PPO iterations would solve these problems, I investigated build probabilities, legal actions, and estimated advantages, then explored replay-informed supervised castle examples and PPO continuation.

The analyzer published here supports that investigation. Its decision-state and visibility checks matter: accidentally reading the post-action owner or an unseen enemy can create misleading supervision.

### 3. Make the deployed path match training

The broader project encountered missing dependency package metadata during submission and inconsistencies in board padding and observation encoding between training and deployment. The response was to add packaging checks, observation-parity checks, and consistent neural-state updates when a heuristic overrode an action.

That integration code is intentionally **not included** in this excerpt because it modifies AverageJoe code whose redistribution license has not been established.

### 4. Avoid repeated evaluation work

Creating fresh JAX functions for repeated matchups led to redundant compilation. The broader project added cached matchup runners, model-load reuse, and a fixed-opponent requirement for multi-checkpoint comparisons. No measured speedup factor is claimed here.

## Historical results — not reproduced here

My experiment log records the following castle-bootstrap continuation results from August 31, 2026:

| EMA checkpoint | Expander-style score | Rusher-style score | Castle-style score | Overall score |
| --- | ---: | ---: | ---: | ---: |
| 4251 | 76.6% | 93.7% | 57.0% | 75.7% |
| **4276** | **82.5%** | **87.5%** | **57.8%** | **75.9%** |
| 4301 | 67.2% | 88.3% | 59.4% | 71.6% |
| 4326 | 75.8% | 88.3% | 50.8% | 71.6% |
| 4351 | 75.8% | 88.9% | 53.1% | 72.5% |
| 4376 | 75.8% | 82.0% | 56.2% | 71.4% |

**Score = (wins + 0.5 × draws) / games**, not win rate. EMA-4276 was selected from these six evaluated candidates; evaluation stopped before two further planned checkpoints. These are recorded local results against scripted/hybrid opponent styles, not leaderboard performance or evidence of superiority to AverageJoe. The weights and complete raw evaluation logs are not shipped, so the figures cannot be independently reproduced from this repository.

Castle-building quality, defense, and obstacle navigation remained weaknesses. Later memory/input variants were experiments, not demonstrated improvements. The repository does not claim that all ideas discussed in the development notes were implemented.

## Scope and attribution

See [PROVENANCE.md](PROVENANCE.md) for the published-file scope and exclusions.

- Upstream research: Matej Straka and Martin Schmid, [*Artificial Generals Intelligence: Mastering Generals.io with Reinforcement Learning*](https://arxiv.org/abs/2507.06825).
- Upstream source: [AverageJoe](https://github.com/strakam/AverageJoe) and [generals-bots](https://github.com/strakam/generals-bots). These are references, not bundled dependencies.
- No upstream source files, paper PDFs, screenshots, model checkpoints, submission ZIPs, or private Git history are included.

This repository is intended for educational and research portfolio review, not production use. That purpose statement is not a general reuse license. No MIT license is declared for this excerpt or claimed for AverageJoe; third-party rights are not granted by this repository.
