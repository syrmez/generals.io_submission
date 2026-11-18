# Public excerpt: scope and provenance

This is a fresh portfolio repository, not a fork or history-preserving export of the full local training project.

## Published material

| File | Origin and scope |
| --- | --- |
| `README.md` | A newly written summary of Xincheng Zhang's development notes and recorded local experiments. Upstream results are distinguished from this project's results. |
| `scripts/top_player_castle_build_stats.py` | The standalone replay-analysis module introduced in the local lab history at commit `724c92b`, with subsequent decision-state/visibility fixes. It uses only Python's standard library, imports no AverageJoe or simulator modules, and is outside both upstream source trees. |
| `tests/test_top_player_castle_build_stats.py` | Tests introduced in the lab history at `ae110e1`, with later fixes. Fixtures are constructed synthetically in the tests; HTTP calls are mocked. |
| `.gitignore` | Local output, environment, cache, and credential exclusions for this public excerpt. |

For publication, player-name and remote replay-ID path validation was tightened and regression tests were added. One synthetic provenance label was made generic. The original full project and its source repositories were not modified by this extraction.

The analysis module's imports, file history, and function names were checked against the locally available AverageJoe and simulator source trees. That review supports publishing it as project-authored standalone tooling; it is not a legal opinion or an exhaustive copyright audit.

## Deliberately excluded

- All files under the original `AverageJoe/` and `generals-bots/` source trees, including modified training, policy, evaluation, and deployment code.
- Heuristic-agent implementations with possible upstream starter-code ancestry.
- Third-party images, screenshots, papers, and READMEs.
- Model weights, replay datasets, submission archives, raw private working notes, and local paths/credentials.
- The full project's Git history, which contains the consolidated upstream sources.

The public repository starts with its own initial commit and uses a GitHub no-reply author email. It is not sufficient to reconstruct or run the full competition agent.

## Upstream licensing context

The AverageJoe source tree, README, and package metadata at [`5041e635dcf6c87b8b844cb2e244ad3e0abe40d7`](https://github.com/strakam/AverageJoe/tree/5041e635dcf6c87b8b844cb2e244ad3e0abe40d7) did not declare a license when checked. GitHub's repository metadata reported `license: null`, and its license endpoint returned 404. No MIT license is inferred from that project's public availability or educational use.

The simulator has its own MIT notice, but that does not establish a license for AverageJoe. Neither upstream codebase is redistributed in this excerpt. Source links and the paper citation in the README acknowledge the foundation of the broader project without claiming authorship or redistributing those artifacts.
