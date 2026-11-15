# Temporal replay verification: Python SDK issue #1578

Reproducible Linux test evidence, recorded 2026-11-15. This repository contains the original workflow and test body from [sdk-python #1578](https://github.com/temporalio/sdk-python/issues/1578), a fixture adapter to run it outside the upstream test suite, versioned workflow definitions, and GitHub Actions artifacts with replay histories, hashes, and execution logs.

## Original reproducer — observed results

The original test runs 20 iterations with two parallel branches and three local activities. Histories are exported to JSON and SHA-256 hashed before replay. Each history is replayed twice.

| Common server | Recorded with | Replay with | Runs | Result |
| --- | --- | --- | --- | --- |
| 1.30.0 (Temporal CLI 1.6.0) | SDK 1.27.2 | SDK 1.27.2 | 4 | 4/4 nondeterminism errors |
| 1.30.0 | SDK 1.27.2 | SDK 1.36.1 | 4 | 4/4 pass |
| 1.30.0 | SDK 1.36.1 | SDK 1.36.1 | 4 | 4/4 pass |
| 1.32.2 (Temporal CLI 1.10.1) | SDK 1.27.2 | SDK 1.27.2 | 4 | 4/4 nondeterminism errors |
| 1.32.2 | SDK 1.27.2 | SDK 1.36.1 | 4 | 4/4 pass |
| 1.32.2 | SDK 1.36.1 | SDK 1.36.1 | 4 | 4/4 pass |

The older replay reports `[TMPRL1100] Nondeterminism error: Activity type of recorded marker 'local_activity_slow' does not match activity type of local activity command 'local_activity_fast'`.

**Conclusion:** Issue #1578 is reproduced using SDK 1.27.2. The same original reproducer is **not reproduced in these SDK 1.36.1 runs**. This is not proof that all past or future histories are safe, nor proof of a particular fixing commit.

- [End-to-end replay evidence, server 1.30.0](https://github.com/lucafranco1994pot-cloud/atlas-temporal-replay-1578/actions/runs/43752679857)
- [End-to-end replay evidence, server 1.32.2](https://github.com/lucafranco1994pot-cloud/atlas-temporal-replay-1578/actions/runs/43751230705)

## Release boundary

The same reproducer, server 1.32.2, four runs per SDK:

| SDK | Original test including replay |
| --- | --- |
| 1.30.0 | 3/4 fail |
| 1.31.0 | 4/4 pass |
| 1.32.0 | 4/4 pass |
| 1.33.0 | 4/4 pass |
| 1.34.0 | 4/4 pass |
| 1.35.0 | 4/4 pass |
| 1.36.0 | 4/4 pass |

The first passing version among those checked is 1.31.0. This narrows the candidate release interval but **does not identify the responsible commit**. Replacing `_shield_await` in 1.31.0 with legacy `asyncio.shield` semantics did not reintroduce the error (4/4 pass in both arms); that isolated change is not sufficient to explain the observed difference.

- [Release boundary runs](https://github.com/lucafranco1994pot-cloud/atlas-temporal-replay-1578/actions/runs/43751426247)
- [Isolated await-semantics comparison](https://github.com/lucafranco1994pot-cloud/atlas-temporal-replay-1578/actions/runs/43751929741)

## Separate regression witness — sdk-rust issue #1623

The three-variant Core test supplied by the reporter of [sdk-rust #1623](https://github.com/temporalio/sdk-rust/issues/1623) was inserted into a temporary checkout of Core commit `c675c32469af707e1c979a7b808c70b4a0608b82` (the exact Python SDK 1.36.1 submodule revision). No upstream repository was changed.

- Activity completion before corresponding WorkflowTaskStarted: FAIL.
- Timer fire before corresponding WorkflowTaskStarted: FAIL.
- Signal before corresponding WorkflowTaskStarted: FAIL.

All three cases expected the history consumer to stop at event 4 but observed it consume through event 6. This is an **own isolated Core-test reproduction**, not end-to-end reproduction of the reporter's timestamp mismatch, and not evidence that it has the same cause as #1578.

[Core regression job and logs](https://github.com/lucafranco1994pot-cloud/atlas-temporal-replay-1578/actions/runs/43752322595)

## Recorded versions and limitations

- Platform: GitHub Actions `ubuntu-22.04`, x86-64, Python 3.11.
- SDK 1.27.2 source tag: `c9e28737bc994ad7b1002f3651aa443bd3303567`; Core Gitlink: `2872b5363e1b745cfb90313ebc7a507c5d25c398`.
- SDK 1.36.1 source tag: `968c3c9dcf508ceca3f4e34b9ea910425351f6c5`; Core Gitlink: `c675c32469af707e1c979a7b808c70b4a0608b82`.
- Python bridge SHA-256, 1.27.2: `d405a2b6c77139fad5930e61c6bd23c681e2460d4c23296fde24ecf6498f7a4b`.
- Python bridge SHA-256, 1.36.1: `292b4753a10762b837073da46619a33e0c7a23a26854d66d5a64150aacbb532b`.
- Temporal CLI 1.6.0 embedded server 1.30.0; executable SHA-256: `c0eab0a51591a991015f4abaeb18be8283e24372ad1d894b92922bdfddf44edb`.
- The originally reported server 1.30.4 was not executed. A shared server executable was held constant within each test matrix.
- The original function and workflow code are unchanged; `new_worker` was supplied by an equivalent minimal test-fixture adapter instead of importing the upstream test suite.
- Captured history JSON is a serialization of the SDK history object, not a raw gRPC response. Artifacts are downloadable from the linked Actions runs but are subject to GitHub artifact-retention limits.
- First divergent activation, detailed workflow timestamp comparison, pagination experiments, chunker-alternative builds, and independent history/command checking remain unverified.

## Acknowledgements

Original #1578 reproducer and report: [paulcacheux](https://github.com/paulcacheux); upstream discussion: [tconley1428](https://github.com/tconley1428) and [Sushisource](https://github.com/Sushisource). The #1623 regression witness is from [mbackschat](https://github.com/mbackschat). The evidence here builds on those contributions and does not claim authorship of their original findings.

This repository does not submit comments, issues, or pull requests to the upstream projects.
