# Enriched Rebuild Experiment

This directory records the retired enriched-card graph rebuild experiment.

The supported v1.1 graph rebuild path is:

```powershell
python main.py rebuild
```

That path rebuilds LightRAG from `output/normalized/`, which remains the source
of truth. Enriched cards stay useful as a separate retrieval/context layer via
card FTS, source registry, wiki memory, and hybrid query context.

The old enriched graph rebuild path was removed from the main CLI because a
controlled full-corpus attempt was slow and unstable, and the clean normalized
rebuild already produced the trusted `23/23` golden result.

If this experiment is revisited, do it on a separate branch/worktree and record:

- why normalized-source rebuild is insufficient;
- expected quality improvement;
- runtime and failure behavior;
- source-selection golden result;
- full golden result;
- recovery steps if `rag_storage/` degrades.

Do not use enriched-card rebuild as a recovery path for v1.1.
