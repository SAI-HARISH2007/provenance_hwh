# Trace `20260830T032653Z_baseline-s02-bad-config-deploy`

- problem: `s02_bad_config_deploy`  model: `gemini-2.5-flash`  sandbox: `simulation`  agent_version: `bf11769`
- status: **success**  score: None  tokens: 21804  wall: 21841 ms
- events: {'run_start': 1, 'instruction': 2, 'llm_request': 1, 'llm_response': 1, 'run_end': 1}

## Timeline

| seq | type | summary |
|---|---|---|
| 1 | run_start |  |
| 2 | instruction | system `baseline_system.md` (1283 chars) |
| 3 | instruction | user `evidence_dump` (30490 chars) |
| 4 | llm_request |  |
| 5 | llm_response | stop; tools=[]; 21602 ms |
| 6 | run_end | success score=None |
