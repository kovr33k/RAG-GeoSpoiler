# F2 Golden Set Attempt

Run started on 2026-05-27 with:

- `QUERY_MODEL=qwen/qwen3-next-80b-a3b-instruct`
- `QUERY_BASE_URL=https://integrate.api.nvidia.com/v1`
- `RERANKER_ENABLED=false`
- `HYBRID_SYNTH_ENABLED=false`
- `HYBRID_QUERY_CARDS_ENABLED=true`
- `WIKI_ENABLED=true`
- `WIKI_TOP_K=5`

The run timed out on Q1 after `QUERY_TIMEOUT_SECONDS=180` and started retrying on Q2.
It was stopped deliberately before it became a long fallback-only run.

See:

- `artifacts/f2_golden_stdout.log`
- `artifacts/f2_golden_stderr.log`
- `LLM_VERIFICATION_QUEUE.md`
