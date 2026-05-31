# Baseline Model Probe

Checked at: 2026-05-27T01:42:27+00:00
Query model: `qwen/qwen3-next-80b-a3b-instruct`
Query base URL: `https://integrate.api.nvidia.com/v1`
Mode: `hybrid`
Cache buster: disabled

## Flags

- RERANKER_ENABLED: False (recommended for E1: False) [OK]
- HYBRID_SYNTH_ENABLED: False (recommended for E1: False) [OK]
- HYBRID_QUERY_CARDS_ENABLED: True (recommended for E1: True) [OK]

## Manual Query Probe

Stable cases: 3/3

### 1. ultra_similarity
- profile: `answer`
- status: `ok`
- duration_seconds: 14.264
- answer_chars: 990
- reference_count: 11
- fallback: ``
- looks_corrupt: False

Answer preview:

В базе данных прямо указано, что ультралевые и ультраправые группы совпадают или сходны по своим характеристикам. Это подтверждается несколькими источниками: в одном из документальных фрагментов говорится: «Ультралевые и ультраправые совпадают» [2], а в другом — «Везде ультралевые и ультраправые одинаковые» [6]. Эти утверждения отражают концепцию синергетического экстремизма, при котором крайние левые и правые идеологии, несмотря на внешние противоречия, могут сходиться в тактике, целях или ф...

### 2. ultra_source
- profile: `source`
- status: `ok`
- duration_seconds: 25.242
- answer_chars: 588
- reference_count: 13
- fallback: ``
- looks_corrupt: False

Answer preview:

Тезис о том, что ультралевые и ультраправые совпадают, присутствует в базе данных и подтверждается следующим источником:

> "Ультралевые и ультраправые совпадают." — [3]

Это утверждение прямо взято из документа с reference_id = 3, который соответствует файлу:  
`D:\ObsidianWiki\GeoSpoiler-RAG\output\normalized\Ультра левые и ультра правые\11.txt`

Также в Knowledge Graph Data подтверждается, что Ultra-Left и Ultra-Right описываются как группы, которые «aligning with» друг друга (сопрягаются...

### 3. trump_orban_support
- profile: `source`
- status: `ok`
- duration_seconds: 19.817
- answer_chars: 1326
- reference_count: 13
- fallback: ``
- looks_corrupt: False

Answer preview:

Да, Дональд Трамп действительно поддерживал Виктора Орбана. Это подтверждается несколькими источниками из предоставленного контекста.

Во-первых, американский политический деятель Мэтт Шлапп, возглавляющий CPAC, поддерживал Виктора Орбана вместе с другими американскими политическими фигурами, включая связь с Трампом, который сам выражал восхищение Орбаном, особенно в вопросах контроля над границами и национального суверенитета. Кроме того, Дональд Трамп-младший публично одобрил Орбана как «пр...
