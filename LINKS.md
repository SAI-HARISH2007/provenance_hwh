# Provenance — everything a reviewer needs, in one place

| What | Link |
|---|---|
| Repository | https://github.com/SAI-HARISH2007/provenance_hwh |
| Live console (incident queue, memory bank, analytics; rendered from the real runs) | https://sai-harish2007.github.io/provenance_hwh/console/ |
| Comparison page (each incident with and without memory, memory panel, gate decisions) | https://sai-harish2007.github.io/provenance_hwh/demo/ |
| Demo video (2½ min, captions included) | https://youtu.be/Ct8z2-jrW4g |
| Reproduce every number with zero API calls | `make eval-replay` (see REPRODUCE.md) |

## Articles and posts

| Member | Article | Post |
|---|---|---|
| Sai Haresh Anand S | https://www.linkedin.com/pulse/i-gave-my-incident-agent-memory-had-top-from-trusting-s-hkbsf/ | https://www.linkedin.com/feed/update/urn:li:activity:7510646382395949056/ |
| Kotam Satya Rithul | https://www.linkedin.com/pulse/building-provenance-what-i-learned-from-making-agent-fail-kotam-6xzaf/ | https://www.linkedin.com/feed/update/urn:li:activity:7510638510173814784/ |
| Seshivardhini Dulam | https://www.linkedin.com/pulse/i-replaced-stateless-agent-runs-hindsight-memory-seshivardhini-dulam-sb1kf/ | https://www.linkedin.com/feed/update/urn:li:activity:7510641778266386434/ |
| Hita Hasini Sakalabhaktula | https://www.linkedin.com/pulse/when-memory-isnt-trust-building-safer-on-call-agent-sakalabhaktula-1ixhf | https://www.linkedin.com/posts/hita-hasini-sakalabhaktula-0b4424392_aiagents-agentmemory-hindsight-ugcPost-7510709365964853248-Kn26/ |

Reddit: https://www.reddit.com/r/LLMDevs/comments/1wt6g5v/

## How Hindsight is used, in one paragraph

Each closed incident is retained as one record with provenance tags (`incident`, `root_cause`, `action`, `verified`, `resolved`, `harm`) and a timestamp weeks apart from the others. Before the first tool call on a new alert, the agent recalls similar incidents with two phrasings, filters on the relevance score, and injects them as claims about the past. A verdict that matches a recalled incident is rejected until a probe in the current incident confirms the mechanism. Details: README §2 and §3, code in `src/greenlight/memory.py` and `src/greenlight/agent/investigator.py`.
