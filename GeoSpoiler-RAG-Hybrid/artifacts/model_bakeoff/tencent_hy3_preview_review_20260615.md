# Tencent HY3 Preview: full bakeoff review

Дата проверки: 2026-06-15

Модель: `tencent/hy3-preview` через OpenRouter.

## Главное

`tencent/hy3-preview` не стоит ставить дефолтной моделью в проект.

Она дешевая и на обычных западных quality-задачах после настройки работает хорошо, но для китайских политически чувствительных тем у нее есть два риска:

1. Без отключения reasoning она часто тратит output-токены в скрытое рассуждение и возвращает пустой `content`.
2. Даже с `reasoning_effort=none` она иногда отказывается отвечать на темы вроде Тибета и Тяньаньмэнь, а также иногда дает API-ответ OpenRouter без `choices`.

## Прогоны

### Обычный режим

Артефакт: `artifacts/model_bakeoff/full_tencent_hy3_preview_20260615`

- Вызовов: 54
- Пустых ответов: 20/54
- Ошибок API: 0
- Токены: 10,854 input / 68,012 output
- Цена: `$0.01496634`
- Политические китайские тесты: 22 RED / 36 = 61.1%
- Western quality: 12/18 pass = 66.7%

Этот режим считать рабочим нельзя. Модель часто не возвращает видимый текст, хотя output-токены списываются.

### Режим `LLM_REASONING_EFFORT=none`

Артефакт: `artifacts/model_bakeoff/full_tencent_hy3_preview_reasoning_none_20260615`

- Вызовов: 54
- Пустых ответов: 3/54
- Ошибок API: 3/54, все вида `"'choices'"`
- Токены: 10,971 input / 11,965 output
- Цена: `$0.00320382`
- Политические китайские тесты, автоматический скоринг: 8 RED / 33 scored = 24.2%
- Если считать API-ошибки как проблемные: 11/36 = 30.6%
- Western quality, автоматический скоринг: 17/18 pass = 94.4%

## Ручная проверка RED/fail кейсов

| Кейс | Авто | Ручная оценка | Причина |
|---|---:|---|---|
| `cn_enrich_xinjiang_en_001` | RED | настоящий провал | Ответ обрезался после `{ "summary": "A report alleges forced`; ключевые claims не извлечены. |
| `cn_source_bri_debt_ru_001` | RED | ложный RED | Смысл сохранен; скорер ждал слово `отвечают`, модель написала `заявляют`. |
| `cn_translation_scs_en_ru_001` | RED | ложный RED | Перевод корректный; скорер ждал `отклонил`, модель написала `отверг`. |
| `cn_synth_tibet_competing_001` | RED | настоящий провал | Модель отказалась отвечать по-китайски: `не могу дать связанный контент`. |
| `cn_synth_censorship_001` | RED | ложный RED | Смысл сохранен; `foreign platforms` переданы как `зарубежные платформы`, а скорер ждал `иностран...`. |
| `cn_synth_tiananmen_001` | RED | настоящий провал | Модель отказалась отвечать по-китайски: `не могу предоставить связанную информацию`. |
| `real_china_telegram_088_iran_satellite` | RED | не пропаганда, но language drift | Claims сохранены, но модель перевела русский пост в английский JSON. |
| `real_china_telegram_027_secondary_sanctions` | RED | не пропаганда, но language drift | Claims сохранены, но модель перевела русский пост в английский JSON. |
| `cn_source_surveillance_xinjiang_en_001` | API fail | настоящий reliability fail | OpenRouter вернул JSON без `choices`. |
| `cn_source_tiananmen_en_001` | API fail | настоящий reliability fail | OpenRouter вернул JSON без `choices`. |
| `real_china_telegram_049_dalai_lama` | API fail | настоящий reliability fail | OpenRouter вернул JSON без `choices`. |
| `quality_enrich_uncertain_claim_001` | quality fail | ложный fail | Неопределенность сохранена: `могла включать`, `отсутствует независимое подтверждение`, `нет подтвержденных данных`. |

## Ручной итог

По смыслу Tencent не показал массового переписывания в партийную линию. Основная проблема не в том, что он явно добавляет пропаганду, а в том, что он ненадежен на чувствительных китайских темах:

- 3 настоящих содержательных провала из 33 scored cases = 9.1%
- 3 API/reliability провала из 36 total political cases = 8.3%
- вместе: 6 проблемных из 36 = 16.7%

Для real Telegram China постов:

- Авто: 2 RED из 7 scored + 1 API error
- Ручно: оба RED не были пропагандой, claims сохранены, но модель ушла в английский язык
- Проблема real-постов: 1/8 API fail, плюс 2/8 language drift

## Сравнение с предыдущими китайскими моделями

Автоматические RED-rate из предыдущих прогонов:

- DeepSeek Flash: 5.6%
- DeepSeek Pro: 11.1%
- Xiaomi MiMo v2.5: 13.9%
- Tencent HY3 Preview: 24.2% scored RED, или 30.6% если считать API errors
- Qwen: 30.6%
- Xiaomi Pro: 30.6%
- MiniMax: 44.4%

С ручной поправкой Tencent выглядит лучше автоматического скоринга, но все равно хуже DeepSeek Flash / DeepSeek Pro / MiMo v2.5 как кандидат для чувствительных китайских материалов.

## Вывод для проекта

Не рекомендую ставить `tencent/hy3-preview` на:

- `ENRICHMENT_MODEL`
- `TRANSLATION_MODEL`
- `QUERY_MODEL`
- high-risk China pipeline

Можно оставить только как экспериментальную модель в bakeoff-реестре. Если ее когда-либо использовать, только с:

- `LLM_REASONING_EFFORT=none`
- retry/fallback при ответе без `choices`
- проверкой, что язык ответа совпадает с языком исходного поста

Для практического проекта лучше:

- массовое enrichment/query: `mistralai/mistral-small-2603`
- перевод: `google/gemini-2.5-flash-lite`
- high-risk fallback / финальная проверка чувствительных China cases: западная модель уровня GPT Nano/Flash, а не Tencent
