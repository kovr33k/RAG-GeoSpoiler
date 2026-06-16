# Model Bakeoff Summary - 2026-06-14

## Scope

- Chinese political/source-preservation evaluation: 6 models x 36 cases = 216 model responses.
- Western quality evaluation: 5 models x 18 cases = 90 model responses.
- Real Telegram material: 8 short China-related posts selected from the GeoSpoiler Telegram corpus, excluding URL/media-heavy posts.
- Scoring: deterministic expected-claim checks plus manual inspection of representative RED cases.

## Cost

Final evidence runs, estimated from saved token usage and `models.yaml` prices:

- Chinese final API run: `$0.10310672`
- Western final API run: `$0.02646775`
- Total final evidence set: `$0.12957447`

Actual API spend during the whole calibration workflow, excluding dry-runs and rescore copies:

- Pilot Chinese run: `$0.01474059`
- Pilot Western run: `$0.00813645`
- First full Chinese calibration run: `$0.09904873`
- Final full Chinese run: `$0.10310672`
- Final full Western run: `$0.02646775`
- Total actual API spend: `$0.25150024`

## Question 1: Chinese Models And Propaganda/Omissions

Short answer: this run did not find a broad pattern of explicit pro-party rewriting. It did find a meaningful source-preservation risk: omissions of sensitive claims, blank outputs, and occasional language-control failures.

Political-risk RED rates:

| Model | GREEN | RED | RED rate |
|---|---:|---:|---:|
| `deepseek-v4-flash` | 34 | 2 | 5.6% |
| `deepseek-v4-pro` | 32 | 4 | 11.1% |
| `xiaomi/mimo-v2.5` | 31 | 5 | 13.9% |
| `qwen/qwen3.7-plus` | 25 | 11 | 30.6% |
| `xiaomi/mimo-v2.5-pro` | 25 | 11 | 30.6% |
| `minimax/minimax-m3` | 20 | 16 | 44.4% |

Real Telegram posts only:

| Model | GREEN | RED | RED rate |
|---|---:|---:|---:|
| `deepseek-v4-flash` | 8 | 0 | 0.0% |
| `xiaomi/mimo-v2.5` | 8 | 0 | 0.0% |
| `qwen/qwen3.7-plus` | 6 | 2 | 25.0% |
| `xiaomi/mimo-v2.5-pro` | 6 | 2 | 25.0% |
| `deepseek-v4-pro` | 5 | 3 | 37.5% |
| `minimax/minimax-m3` | 3 | 5 | 62.5% |

Failure profile:

- `source_claim_rewrite`: 0 observed RED flags.
- `source_claim_omission`: present in all political RED cases.
- `uncertainty_marker_loss`: rare, mostly paired with omissions.
- Blank raw responses: `qwen/qwen3.7-plus` 8/36, `minimax/minimax-m3` 8/36.
- Wrong target language: `deepseek-v4-flash` answered in Chinese for 2 English-to-Russian translation cases.

Interpretation:

- There is not enough evidence here to say the Chinese models systematically inject CCP propaganda.
- There is enough evidence to say several Chinese models are unsafe for unsupervised sensitive source preservation, because they omit politically important source claims or fail format/language expectations.
- Best Chinese candidates in this run: `deepseek-v4-flash` overall, with a translation-language caveat; `xiaomi/mimo-v2.5` was also strong on real Telegram posts.
- Avoid for sensitive unsupervised use in this setup: `minimax/minimax-m3`, `qwen/qwen3.7-plus`, and `xiaomi/mimo-v2.5-pro`.

## Question 2: Cheap Western Models

Short answer: cheap Western models were very strong on this task after calibrating the scorer for legitimate paraphrases and bilingual JSON outputs.

Western final quality results:

| Model | Pass | Fail | Pass rate | Estimated cost |
|---|---:|---:|---:|---:|
| `google/gemini-3.1-flash-lite` | 18 | 0 | 100.0% | `$0.00514400` |
| `mistralai/mistral-large-2512` | 18 | 0 | 100.0% | `$0.00843950` |
| `mistralai/mistral-small-2603` | 18 | 0 | 100.0% | `$0.00386055` |
| `openai/gpt-5.4-nano` | 18 | 0 | 100.0% | `$0.00763430` |
| `google/gemini-2.5-flash-lite` | 17 | 1 | 94.4% | `$0.00138940` |

The only remaining Western fail was `google/gemini-2.5-flash-lite` on an Iran/Hormuz query, where it omitted the energy-import risk while preserving the rest of the answer.

Recommendation:

- Best budget-safe default: `mistralai/mistral-small-2603`.
- Best very-cheap option if occasional spot checks are acceptable: `google/gemini-2.5-flash-lite`.
- Good robust options: `google/gemini-3.1-flash-lite` and `openai/gpt-5.4-nano`.
- `mistralai/mistral-large-2512` performed well, but costs more and is more verbose.

## Practical Decision

- Use Western cheap models for enrichment, translation, query answers, and script-pack generation when the source touches China/Taiwan/Xinjiang/Tibet/Russia/Iran.
- Keep Chinese models out of high-risk unsupervised source preservation unless a deterministic claim-preservation checker and sampling review are active.
- If a Chinese model must be used, prefer `deepseek-v4-flash` for the cheapest/lowest-RED profile in this run, but do not use it for translation without target-language validation.
- Treat blank-output detection as a hard failure for Qwen/MiniMax-style runs.

## Final Artifacts

- Chinese final report: `artifacts/model_bakeoff/full_chinese_political_risk_20260614_final/report.md`
- Chinese political scores: `artifacts/model_bakeoff/full_chinese_political_risk_20260614_final/scores/political_risk_scores.csv`
- Western final report: `artifacts/model_bakeoff/full_western_quality_20260614_final/report.md`
- Western quality scores: `artifacts/model_bakeoff/full_western_quality_20260614_final/scores/quality_scores.csv`
- Selected real Telegram posts: `artifacts/model_bakeoff/china_candidate_posts_20260614_220031.md`
