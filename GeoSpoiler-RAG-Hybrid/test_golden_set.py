import asyncio
import io
import json
import sys
from pathlib import Path
from typing import Any

import config
from loader.lightrag_loader import create_rag, query_rag_result
from main import _extract_query_sources, _question_requests_sources

_TECHNICAL_FORBIDDEN = [
    "lightrag не поднял",
    "точный поиск по карточкам",
    "shadow_search",
    "fallback",
]

_VISUAL_QUERY_TERMS = ["визуал", "кадр", "b-roll", "broll", "ролик", "сцена", "видео"]


GOLDEN_CASES: list[dict[str, Any]] = [
    {
        "question": "Что в базе говорится о сходстве ультралевых и ультраправых?",
        "must": ["ультралев", "ультраправ", "совпад"],
        "must_not": ["идеологическая теория", "нет информации", "отсутствует информация"],
        "source_any": ["Ультра левые и ультра правые\\11.txt", "3299898370/11"],
    },
    {
        "question": "Откуда в базе тезис про ультралевых и ультраправых? Дай ссылку.",
        "profile": "source",
        "must": ["ультралев", "ультраправ"],
        "source_required": True,
    },
    {
        "question": "Что в базе говорится про связи европейских ультраправых с Трампом?",
        "must": ["трамп", "ультраправ"],
        "must_not": ["все европейские партии", "фальш", "дезинформац", "якобы"],
    },
    {
        "question": "Почему в базе AfD выглядит проблемной партией?",
        "must": ["afd", "украин"],
        "must_not": ["доказано, что afd"],
    },
    {
        "question": "Что в базе говорится про отношение AfD к войне в Украине?",
        "must": ["afd", "украин", "помощ"],
        "must_not": ["все ультраправые"],
    },
    {
        "question": "Что в базе говорится о риске утечки информации от AfD к России?",
        "must": ["afd", "росси", "подоз"],
        "must_not": ["доказан", "установлено, что afd передала"],
    },
    {
        "question": "Что в базе говорится о Кубе и переговорах с США?",
        "must": ["куб", "сша", "переговор"],
        "must_not": ["afd", "ультраправ", "нет информации", "отсутствует информация"],
        "source_any": ["Куба\\5.txt", "Куба\\8.txt", "3841808641/5", "3841808641/8"],
    },
    {
        "question": "Что в базе говорится о поставках нефти на Кубу и позиции Трампа?",
        "must": ["нефт", "куб", "трамп"],
        "must_not": ["afd", "ультраправ"],
    },
    {
        "question": "Что в базе говорится о протестах на Кубе?",
        "must": ["куб", "протест", "электр"],
        "must_not": ["afd", "ультраправ", "нет информации", "отсутствует информация"],
        "source_any": ["Куба\\5.txt", "3841808641/5"],
    },
    {
        "question": "Как база описывает отношение США к Кубе: давление или попытку сделки?",
        "must": ["сша", "куб", "давлен", "переговор"],
        "must_not": [
            "военные действия против Кубы без одобрения Конгресса",
            "нет информации",
            "отсутствует информация",
        ],
        "source_any": ["Куба\\8.txt", "3841808641/8"],
    },
    {
        "question": "Какие страны или регионы чаще всего фигурируют в теме ультраправых?",
        "profile": "overview",
        "must": ["герман", "росси"],
        "must_not": ["швеция", "молдова"],
    },
    {
        "question": "Что в базе говорится про связь ультраправых с Россией?",
        "must": ["ультраправ", "росси"],
        "must_not": ["все связаны с россией"],
    },
    {
        "question": "Что в базе говорится о риске российского вторжения в страны Балтии?",
        "must": ["балти", "росси", "нато"],
        "must_not": ["точная дата вторжения"],
    },
    {
        "question": "Что в базе говорится о Нарве и планах России против Эстонии?",
        "must": ["нарв", "эстон", "росси"],
        "must_not": ["нарва уже захвачена", "нет информации", "отсутствует информация"],
        "source_any": ["Балтийские страны\\2.txt", "Балтийские страны\\4.txt", "3889026624/2", "3889026624/4"],
    },
    {
        "question": "Как база описывает позицию Орбана по Украине и поддержке ЕС?",
        "must": ["орбан", "украин", "поддерж"],
        "must_not": ["орбан поддерживает вступление украины"],
    },
    {
        "question": "Что в базе говорится о Фицо и политическом кризисе в Словакии?",
        "must": ["фицо", "слова", "премьер"],
        "must_not": ["фицо ушёл в отставку"],
    },
    {
        "question": "Что в базе говорится о северокорейских военных и России?",
        "must": ["северокор", "росси", "военн"],
        "must_not": ["южная корея отправила войска в россию"],
    },
    {
        "question": "Откуда в базе тезис про северокорейских военных в России? Дай ссылку.",
        "profile": "source",
        "must": ["северокор", "росси"],
        "source_required": True,
    },
    {
        "question": "Что в базе говорится о Британии, Стармере и оборонном сотрудничестве с ЕС?",
        "must": ["британ", "стармер", "ес"],
        "must_not": ["британия вернулась в ес"],
    },
    {
        "question": "Что в базе говорится о трещинах в отношениях США и Великобритании при Трампе и Стармере?",
        "must": ["сша", "великобрит", "трамп", "стармер"],
        "must_not": ["разрыв дипломатических отношений"],
    },
    {
        "question": "Кто финансирует AfD?",
        "must": ["отсутств", "нельзя определить"],
        "must_not": ["россия финансирует", "кремль финансирует"],
    },
    {
        "question": "Какие кадры или визуалы можно использовать для ролика про Нарву и Эстонию?",
        "must": ["визуал", "кадр", "нарв"],
        "must_not": ["нельзя определить", "отсутствует информация"],
        "source_any": ["Балтийские страны\\2.txt", "Балтийские страны\\4.txt", "3889026624/2", "3889026624/4"],
    },
    {
        "question": "Какой главный тезис о Кубе и её экономике продвигает автор?",
        "must": ["тезис", "экономик", "куб"],
        "must_not": ["ультраправ"],
    },
]


def _score_answer(answer: str, sources: list[dict[str, str]], case: dict[str, Any]) -> dict[str, Any]:
    text = answer.casefold()
    question = str(case.get("question", ""))
    visual_question = any(term in question.casefold() for term in _VISUAL_QUERY_TERMS)
    common_forbidden = list(_TECHNICAL_FORBIDDEN)
    if not visual_question:
        common_forbidden.extend(["b-roll", "broll", "b-roll/визуал", "визуальные материалы"])
    must_not = list(case.get("must_not", [])) + common_forbidden

    missing = [term for term in case.get("must", []) if term.casefold() not in text]
    forbidden = [term for term in must_not if term.casefold() in text]
    source_required = bool(case.get("source_required"))
    source_ok = not source_required or any(source.get("post_url") or source.get("file_path") for source in sources)
    source_any = case.get("source_any", [])
    source_blob = "\n".join(
        f"{source.get('post_url', '')}\n{source.get('file_path', '')}"
        for source in sources
    ).casefold()
    source_any_ok = not source_any or any(term.casefold() in source_blob for term in source_any)

    score = 100
    score -= 20 * len(missing)
    score -= 25 * len(forbidden)
    if not source_ok:
        score -= 30
    if not source_any_ok:
        score -= 30
    score = max(0, score)

    return {
        "score": score,
        "pass": score >= 80 and not missing and not forbidden and source_ok and source_any_ok,
        "missing": missing,
        "forbidden": forbidden,
        "source_required": source_required,
        "source_ok": source_ok,
        "source_any": source_any,
        "source_any_ok": source_any_ok,
        "sources": sources,
    }


async def run_tests():
    rag = await create_rag()

    results_file = Path("artifacts/golden_set_results.md")
    scores_file = Path("artifacts/golden_set_scores.json")
    results_file.parent.mkdir(exist_ok=True)

    scores = []
    try:
        with results_file.open("w", encoding="utf-8") as f:
            f.write("# Golden Set Results\n\n")
            f.write("Default profile: answer/top_k=15. Source questions use source/top_k=15. Overview questions use overview/top_k=30.\n\n")

            for i, case in enumerate(GOLDEN_CASES, 1):
                question = case["question"]
                profile = case.get("profile") or ("source" if _question_requests_sources(question) else "answer")
                print(f"Running Q{i}/{len(GOLDEN_CASES)} [{profile}]")
                f.write(f"## {i}. {question}\n\n")
                f.write(f"Profile: `{profile}`\n\n")

                try:
                    query_result = await query_rag_result(rag, question, mode="mix", query_profile=profile)
                    answer = str(query_result.get("llm_response", {}).get("content") or "").strip()
                    sources = _extract_query_sources(query_result)
                except Exception as exc:
                    answer = f"ERROR: {exc}"
                    sources = []

                score = _score_answer(answer, sources, case)
                score_record = {
                    "question": question,
                    "profile": profile,
                    **score,
                }
                scores.append(score_record)

                f.write(answer + "\n\n")
                if sources:
                    f.write("### Resolved Sources\n")
                    for idx, source in enumerate(sources, 1):
                        label = source.get("post_url") or source.get("file_path") or "unknown"
                        f.write(f"- [{idx}] {label}\n")
                    f.write("\n")
                f.write("### Score\n")
                f.write(f"- score: {score['score']}\n")
                f.write(f"- pass: {score['pass']}\n")
                if score["missing"]:
                    f.write(f"- missing: {', '.join(score['missing'])}\n")
                if score["forbidden"]:
                    f.write(f"- forbidden: {', '.join(score['forbidden'])}\n")
                if score["source_required"]:
                    f.write(f"- source_ok: {score['source_ok']}\n")
                if score["source_any"]:
                    f.write(f"- source_any_ok: {score['source_any_ok']}\n")
                f.write("\n")
    finally:
        try:
            await asyncio.wait_for(
                rag.finalize_storages(),
                timeout=config.RAG_FINALIZE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            print(
                f"WARNING: LightRAG finalize timed out after "
                f"{config.RAG_FINALIZE_TIMEOUT_SECONDS}s"
            )

    summary = {
        "total": len(scores),
        "passed": sum(1 for item in scores if item["pass"]),
        "failed": sum(1 for item in scores if not item["pass"]),
        "average_score": round(sum(item["score"] for item in scores) / max(1, len(scores)), 1),
        "cases": scores,
    }
    scores_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Golden set: {summary['passed']}/{summary['total']} passed, avg={summary['average_score']}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    asyncio.run(run_tests())
