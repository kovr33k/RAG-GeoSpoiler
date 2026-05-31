# Experiment Registry

- generated_at: 2026-05-31T17:52:52+00:00
- records: 9

| Checked At | Kind | Model | Mode | Passed | Avg | Rerank | Synth | Wiki | Scores |
|---|---|---|---|---:|---:|:---:|:---:|:---:|---|
| 2026-05-27T02:03:18+00:00 | golden | qwen/qwen3-next-80b-a3b-instruct | hybrid | 22/23 | 98.7 | N | N | n/a | `e2_baseline_golden_set_scores.json` |
| 2026-05-27T02:03:18+00:00 | golden | qwen/qwen3-next-80b-a3b-instruct | hybrid | 22/23 | 98.7 | N | N | n/a | `golden_set_scores.json` |
| 2026-05-30T15:36:40+00:00 | focused_probe | deepseek-v4-flash | hybrid | 5/6 | 93.3 | N | Y | Y | `llm_probe_deepseek_v4_flash_clearcache_scores.json` |
| 2026-05-30T15:43:31+00:00 | focused_probe | deepseek-v4-flash | hybrid | 6/6 | 100 | N | Y | Y | `llm_probe_deepseek_v4_flash_absence_fix_clearcache_scores.json` |
| 2026-05-30T16:01:10+00:00 | scores | deepseek-v4-flash | hybrid | 2/2 | 100 | N | Y | Y | `deepseek_v4_flash_clearcache_smoke_scores.json` |
| 2026-05-30T16:14:11+00:00 | golden | deepseek-v4-flash | hybrid | 23/23 | 100 | N | Y | Y | `deepseek_v4_flash_clearcache_golden_set_scores.json` |
| 2026-05-30T17:31:19+00:00 | golden | deepseek-v4-flash | hybrid | 23/23 | 100 | N | Y | Y | `deepseek_v4_flash_rebuilt_clearcache_golden_set_scores.json` |
| 2026-05-31T15:06:29+00:00 | golden | deepseek-v4-flash | mix | 20/23 | 96.7 | Y | Y | Y | `deepseek_v4_flash_reranker_clearcache_golden_set_scores.json` |
| 2026-05-31T17:52:33+00:00 | golden | deepseek-v4-flash | hybrid | 3/3 | 100 | N | Y | Y | `pre_commit_golden_smoke_scores.json` |
