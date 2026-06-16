# Model Bakeoff Failures

## openai/gpt-5.4-nano / rag_build_metadata_noise_001

- quality_score: 75
- missing: -
- forbidden: GeoSpoiler China

## mistralai/mistral-small-2603 / rag_build_conflicting_claims_001

- quality_score: 85
- missing: any of: does not decide | no conclusion | not decide
- forbidden: -

## google/gemini-3.1-flash-lite / rag_build_quote_preservation_001

- quality_score: 70
- missing: any of: проверкой судов | ship inspections | vessel inspections, эта мера создает юридическую серую зону
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_conflict_sources_001

- quality_score: 70
- missing: source_a, source_b
- forbidden: -

## mistralai/mistral-small-2603 / fallback_conflict_sources_001

- quality_score: 55
- missing: source_a, source_b, any of: расход | конфликт | разные версии
- forbidden: -

## openai/gpt-5.4-nano / fallback_conflict_sources_001

- quality_score: 85
- missing: any of: расход | конфликт | разные версии
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_source_request_001

- quality_score: 85
- missing: Китай/88.txt
- forbidden: -

## mistralai/mistral-small-2603 / fallback_source_request_001

- quality_score: 85
- missing: Китай/88.txt
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_uncertainty_dual_use_001

- quality_score: 70
- missing: any of: нет доказательств | не доказано | does not prove, any of: знал | знании | knowledge
- forbidden: -

## mistralai/mistral-small-2603 / fallback_uncertainty_dual_use_001

- quality_score: 85
- missing: any of: нет доказательств | не доказано | does not prove
- forbidden: -

## openai/gpt-5.4-nano / fallback_uncertainty_dual_use_001

- quality_score: 85
- missing: any of: нет доказательств | не доказано | does not prove
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_overview_country_list_001

- quality_score: 70
- missing: США, any of: дронах | drones
- forbidden: -

## mistralai/mistral-small-2603 / fallback_overview_country_list_001

- quality_score: 70
- missing: США, any of: дронах | drones
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_taiwan_quarantine_001

- quality_score: 55
- missing: source_a, source_b, any of: провер | inspection
- forbidden: -

## mistralai/mistral-small-2603 / fallback_taiwan_quarantine_001

- quality_score: 55
- missing: source_a, source_b, any of: провер | inspection
- forbidden: -

## openai/gpt-5.4-nano / fallback_taiwan_quarantine_001

- quality_score: 70
- missing: source_a, source_b
- forbidden: -

## openai/gpt-5.4-nano / fallback_noisy_context_no_internal_terms_001

- quality_score: 40
- missing: any of: Пекин | Beijing | Китай, any of: Тайван | Taiwan, any of: военное давление | military pressure, any of: принудитель | coercive
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_refuse_to_overstate_001

- quality_score: 70
- missing: any of: не доказывает | does not prove | не следует, any of: Financial Times | FT
- forbidden: -

## mistralai/mistral-small-2603 / fallback_refuse_to_overstate_001

- quality_score: 70
- missing: any of: не доказывает | does not prove | не следует, any of: Financial Times | FT
- forbidden: -

## openai/gpt-5.4-nano / fallback_refuse_to_overstate_001

- quality_score: 85
- missing: any of: Financial Times | FT
- forbidden: -
