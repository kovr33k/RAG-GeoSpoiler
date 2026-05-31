# Golden Set Results

Checked at: 2026-05-31T22:39:07+00:00

Query model: `deepseek-v4-flash`

Query base URL: `https://api.deepseek.com`

Mode: `hybrid`

Flags: `RERANKER_ENABLED=False`, `HYBRID_SYNTH_ENABLED=True`, `HYBRID_QUERY_CARDS_ENABLED=True`, `WIKI_ENABLED=True`, `WIKI_TOP_K=5`

Default profile: answer/top_k=15. Source questions use source/top_k=15. Overview questions use overview/top_k=30.

## 1. Что в базе говорится о риске утечки информации от AfD к России?

Profile: `answer`

AfD (АдГ): Согласно имеющейся информации, немецкую ультраправую партию «Альтернатива для Германии» (АдГ) подозревают в передаче секретных документов Евросоюза России. Об этом сообщает издание Politico.

В частности, политиков от АдГ подозревают в раскрытии информации, которая могла представлять интерес для российской разведки. Речь идет о сведениях, касающихся местной противодроновой обороны, западных поставок оружия Украине, а также осведомленности властей о российской диверсионной и гибридной деятельности в регионе Балтийского моря.

### Resolved Sources
- [1] https://t.me/c/3215620297/26
- [2] https://t.me/c/3328128766/98
- [3] https://t.me/c/3215620297/15
- [4] https://t.me/c/3299898370/19
- [5] https://t.me/c/3328128766/14

### Score
- score: 100
- pass: True

