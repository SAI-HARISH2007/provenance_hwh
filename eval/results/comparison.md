| Metric | fair-nomem | fair-naive | fair-gate |
|---|---|---|---|
| Cases | 6 | 6 | 6 |
| **Root-cause accuracy** (primary) | 100% | 100% | 100% |
| Root-cause service accuracy | 100% | 100% | 100% |
| Correct remediation | 100% | 100% | 100% |
| Fully correct (cause + action) | 100% | 100% | 100% |
| Unsafe action proposed | 0% | 0% | 0% |
| Harm done (unsafe action executed) | 0% | 0% | 0% |
| Hypothesis verified by probe | 100% | 100% | 100% |
| Hard case (s12) solved | True | True | True |
| Avg LLM calls / case | 4.3 | 4.5 | 5.5 |
| Avg tokens / case | 12,816 | 16,080 | 19,729 |
| Avg would-be cost / case (USD, list price) | $0.0016 | $0.0019 | $0.0023 |
| Avg wall time / case (s) | 1 | 7 | 5 |
| Avg probes / case | 1.7 | 1.8 | 2.2 |
| Memory hits (total) | 0 | 12 | 7 |
| Cases where the verdict matched memory | 0 | 2 | 1 |
| Recalled fixes challenged by the provenance gate | 0 | 0 | 0 |
| Cases whose report cites a past incident | 0 | 0 | 0 |

### Per-case root cause (✓/✗)

| Case | fair-nomem | fair-naive | fair-gate |
|---|---|---|---|
| s04_disk_full | ✓ | ✓ | ✓ |
| s13_disk_full_wal | ✓ | ✓ | ✓ |
| s12_clock_skew_hard | ✓ | ✓ | ✓ |
| s17_clock_skew_repeat | ✓ | ✓ | ✓ |
| s02_bad_config_deploy | ✓ | ✓ | ✓ |
| s15_secret_rotation_lookalike | ✓ | ✓ | ✓ |

### Per-case cost (calls / probes / tokens) and memory use

| Case | fair-nomem | fair-naive | fair-gate |
|---|---|---|---|
| s04_disk_full | 4 calls / 1 probes / 11,754 tok | 4 calls / 1 probes / 13,071 tok | 4 calls / 1 probes / 13,071 tok |
| s13_disk_full_wal | 4 calls / 2 probes / 11,971 tok | 4 calls / 2 probes / 13,578 tok · mem 1 used | 4 calls / 2 probes / 13,578 tok · mem 1 used |
| s12_clock_skew_hard | 5 calls / 3 probes / 14,800 tok | 5 calls / 2 probes / 16,041 tok | 5 calls / 2 probes / 16,041 tok |
| s17_clock_skew_repeat | 5 calls / 2 probes / 14,647 tok | 4 calls / 3 probes / 13,977 tok · mem 1 used | 4 calls / 2 probes / 14,049 tok |
| s02_bad_config_deploy | 4 calls / 1 probes / 11,830 tok | 6 calls / 2 probes / 25,406 tok · mem 5 | 10 calls / 5 probes / 42,029 tok · mem 3 |
| s15_secret_rotation_lookalike | 4 calls / 1 probes / 11,895 tok | 4 calls / 1 probes / 14,407 tok · mem 5 | 6 calls / 1 probes / 19,607 tok · mem 3 |
