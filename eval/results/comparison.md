| Metric | baseline | final |
|---|---|---|
| Cases | 16 | 16 |
| **Root-cause accuracy** (primary) | 81% | 100% |
| Root-cause service accuracy | 88% | 94% |
| Correct remediation | 81% | 81% |
| Fully correct (cause + action) | 75% | 81% |
| Unsafe action proposed | 0% | 0% |
| Harm done (unsafe action executed) | 0% | 0% |
| Hypothesis verified by probe | 0% | 100% |
| Hard case (s12) solved | False | True |
| Avg LLM calls / case | 1.0 | 5.8 |
| Avg tokens / case | 5,368 | 20,027 |
| Avg would-be cost / case (USD, list price) | $0.0007 | $0.0024 |
| Avg wall time / case (s) | 0 | 0 |
| Avg probes / case | 0.0 | 1.4 |
| Memory hits (total) | 0 | 0 |
| Cases where the verdict matched memory | 0 | 0 |
| Recalled fixes challenged by the provenance gate | 0 | 0 |
| Cases whose report cites a past incident | 0 | 0 |

### Per-case root cause (✓/✗)

| Case | baseline | final |
|---|---|---|
| s01_db_pool_exhausted | ✓ | ✓ |
| s02_bad_config_deploy | ✓ | ✓ |
| s03_tls_cert_expired | ✓ | ✓ |
| s04_disk_full | ✓ | ✓ |
| s05_third_party_outage | ✓ | ✓ |
| s06_memory_leak_oom | ✓ | ✓ |
| s07_cache_eviction_stampede | ✓ | ✓ |
| s08_third_party_rate_limited | ✓ | ✓ |
| s09_dns_resolution_failure | ✗ | ✓ |
| s10_migration_lock_contention | ✓ | ✓ |
| s11_feature_flag_misconfig | ✓ | ✓ |
| s12_clock_skew_hard | ✗ | ✓ |
| s13_disk_full_wal | ✓ | ✓ |
| s15_secret_rotation_lookalike | ✓ | ✓ |
| s16_poison_message | ✓ | ✓ |
| s17_clock_skew_repeat | ✗ | ✓ |
