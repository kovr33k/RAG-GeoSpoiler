# Model Bakeoff Failures

## google/gemini-3.1-flash-lite / fallback_conflict_sources_001

- quality_score: 70
- missing: source_a, source_b
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_overview_country_list_001

- quality_score: 70
- missing: США, any of: дронах | drones
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_refuse_to_overstate_001

- quality_score: 70
- missing: any of: не доказывает | does not prove | не следует, any of: Financial Times | FT
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_source_request_001

- quality_score: 85
- missing: Китай/88.txt
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_taiwan_quarantine_001

- quality_score: 55
- missing: source_a, source_b, any of: провер | inspection
- forbidden: -

## google/gemini-3.1-flash-lite / fallback_uncertainty_dual_use_001

- quality_score: 70
- missing: any of: нет доказательств | не доказано | does not prove, any of: знал | знании | knowledge
- forbidden: -

## google/gemini-3.1-flash-lite / rag_build_quote_preservation_001

- quality_score: 70
- missing: any of: проверкой судов | ship inspections | vessel inspections, эта мера создает юридическую серую зону
- forbidden: -

## google/gemini-3.1-flash-lite / rag_build_sanctions_controls_001

- quality_score: 85
- missing: any of: не утверждает | does not claim
- forbidden: -

## mistralai/mistral-small-2603 / fallback_overview_country_list_001

- quality_score: 85
- missing: США
- forbidden: -

## mistralai/mistral-small-2603 / fallback_refuse_to_overstate_001

- quality_score: 55
- missing: any of: не доказывает | does not prove | не следует, any of: Financial Times | FT, any of: КСИР | IRGC
- forbidden: -

## mistralai/mistral-small-2603 / fallback_source_request_001

- quality_score: 85
- missing: Financial Times
- forbidden: -

## mistralai/mistral-small-2603 / fallback_taiwan_quarantine_001

- quality_score: 85
- missing: any of: провер | inspection
- forbidden: -

## mistralai/mistral-small-2603 / fallback_uncertainty_dual_use_001

- quality_score: 85
- missing: any of: нет доказательств | не доказано | does not prove
- forbidden: -

## mistralai/mistral-small-2603 / rag_build_conflicting_claims_001

- quality_score: 85
- missing: any of: does not decide | no conclusion | not decide
- forbidden: -

## openai/gpt-5.4-nano / fallback_noisy_context_no_internal_terms_001

- quality_score: 75
- missing: -
- forbidden: output/enriched

## openai/gpt-5.4-nano / fallback_overview_country_list_001

- quality_score: 85
- missing: США
- forbidden: -

## openai/gpt-5.4-nano / fallback_refuse_to_overstate_001

- quality_score: 85
- missing: any of: Financial Times | FT
- forbidden: -

## openai/gpt-5.4-nano / fallback_uncertainty_dual_use_001

- quality_score: 85
- missing: any of: нет доказательств | не доказано | does not prove
- forbidden: -
