import sys
import shutil
import unittest
import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from loader import lightrag_loader  # noqa: E402
from loader.lightrag_loader import (  # noqa: E402
    _postprocess_extraction_response,
    _postprocess_answer_text,
    _attach_card_context,
    _answer_looks_corrupt,
    _card_context_for_query,
    _shadow_fallback_result,
    _synthesize_hybrid_result,
    _source_doc_id,
    get_query_profile,
    load_from_enriched,
    load_texts,
)


class _FakeDocStatus:
    def __init__(self, existing_ids=None):
        self._existing_ids = {doc_id: {"status": "processed"} for doc_id in (existing_ids or [])}

    async def get_by_id(self, doc_id: str):
        return self._existing_ids.get(doc_id)

    def remove(self, doc_id: str):
        self._existing_ids.pop(doc_id, None)


class _FakeRag:
    def __init__(self, existing_ids=None):
        self.doc_status = _FakeDocStatus(existing_ids)
        self.deleted = []
        self.inserted = []

    async def adelete_by_doc_id(self, doc_id: str):
        self.deleted.append(doc_id)
        self.doc_status.remove(doc_id)
        return SimpleNamespace(status="success", message="deleted")

    async def ainsert(self, texts, ids=None, file_paths=None):
        self.inserted.append(
            {
                "texts": texts,
                "ids": ids,
                "file_paths": file_paths,
            }
        )


class _HangingRag(_FakeRag):
    async def ainsert(self, texts, ids=None, file_paths=None):
        self.inserted.append(
            {
                "texts": texts,
                "ids": ids,
                "file_paths": file_paths,
            }
        )
        await asyncio.Event().wait()


class _FailedStatusRag(_FakeRag):
    async def ainsert(self, texts, ids=None, file_paths=None):
        await super().ainsert(texts, ids=ids, file_paths=file_paths)
        for doc_id in ids or []:
            self.doc_status._existing_ids[doc_id] = {"status": "failed"}


class LoadTextsTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_texts_uses_stable_path_based_doc_ids(self):
        path = str((Path(__file__).parent / "output" / "normalized" / "topic" / "1.txt").resolve())
        rag = _FakeRag()

        inserted = await load_texts(rag, [(path, "hello world")], batch_size=5)

        self.assertEqual(inserted, 1)
        self.assertEqual(rag.deleted, [])
        self.assertEqual(len(rag.inserted), 1)
        self.assertEqual(rag.inserted[0]["ids"], [_source_doc_id(path)])
        self.assertEqual(rag.inserted[0]["file_paths"], [path])
        self.assertEqual(rag.inserted[0]["texts"], ["hello world"])

    async def test_load_texts_strips_headers_and_placeholders_before_insert(self):
        path = str((Path(__file__).parent / "output" / "normalized" / "topic" / "3.txt").resolve())
        rag = _FakeRag()
        text = (
            "[Канал: Topic | Дата: 2026-04-30 12:00 | Пост: https://t.me/example/3]\n\n"
            "Useful body.\n\n"
            "[Видео: пост содержал видео - не обработано]\n"
            "[AI-диалог: https://chatgpt.com/share/abc]\n"
        )

        inserted = await load_texts(rag, [(path, text)], batch_size=5)

        self.assertEqual(inserted, 1)
        self.assertEqual(rag.inserted[0]["texts"], ["Useful body."])

    async def test_load_texts_writes_source_metadata_index(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "source_index_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            rag_storage_dir = temp_root / "rag_storage"
            rag_storage_dir.mkdir(parents=True, exist_ok=True)
            topic_dir = temp_root / "normalized" / "topic"
            topic_dir.mkdir(parents=True, exist_ok=True)

            txt_path = topic_dir / "4.txt"
            txt_path.write_text("Body", encoding="utf-8")
            meta_path = topic_dir / "4.meta.json"
            meta_path.write_text(
                json.dumps({"post_url": "https://t.me/example/4", "channel_name": "Topic"}, ensure_ascii=False),
                encoding="utf-8",
            )

            rag = _FakeRag()
            with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", rag_storage_dir):
                inserted = await load_texts(rag, [(str(txt_path), "Body")], batch_size=5)

            self.assertEqual(inserted, 1)
            index_path = rag_storage_dir / "doc_metadata_index.json"
            self.assertTrue(index_path.exists())
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            only_value = next(iter(data.values()))
            self.assertEqual(only_value["post_url"], "https://t.me/example/4")
            self.assertEqual(only_value["channel_name"], "Topic")
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    async def test_load_texts_replaces_existing_document_for_same_path(self):
        path = str((Path(__file__).parent / "output" / "normalized" / "topic" / "2.txt").resolve())
        existing_doc_id = _source_doc_id(path)
        rag = _FakeRag(existing_ids=[existing_doc_id])

        inserted = await load_texts(rag, [(path, "updated text")], batch_size=5)

        self.assertEqual(inserted, 1)
        self.assertEqual(rag.deleted, [existing_doc_id])
        self.assertEqual(rag.inserted[0]["ids"], [existing_doc_id])
        self.assertEqual(rag.inserted[0]["texts"], ["updated text"])

    async def test_load_texts_skips_timed_out_document_and_writes_report(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "timeout_insert_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            rag_storage_dir = temp_root / "rag_storage"
            rag_storage_dir.mkdir(parents=True, exist_ok=True)
            path = str((temp_root / "normalized" / "topic" / "slow.txt").resolve())
            rag = _HangingRag()

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", rag_storage_dir):
                    with patch.object(lightrag_loader.config, "RAG_INSERT_TIMEOUT_SECONDS", 0.01):
                        inserted = await load_texts(rag, [(path, "slow body")], batch_size=1)

            self.assertEqual(inserted, 0)
            self.assertEqual(rag.deleted, [_source_doc_id(path)])
            report_path = temp_root / "artifacts" / "rag_insert_skipped.md"
            self.assertTrue(report_path.exists())
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("insert timeout after", report)
            self.assertIn("slow.txt", report)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    async def test_load_texts_skips_lightrag_failed_status(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "failed_status_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            rag_storage_dir = temp_root / "rag_storage"
            rag_storage_dir.mkdir(parents=True, exist_ok=True)
            path = str((temp_root / "normalized" / "topic" / "failed.txt").resolve())
            rag = _FailedStatusRag()

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", rag_storage_dir):
                    inserted = await load_texts(rag, [(path, "body")], batch_size=1)

            self.assertEqual(inserted, 0)
            self.assertEqual(rag.deleted, [_source_doc_id(path)])
            report_path = temp_root / "artifacts" / "rag_insert_skipped.md"
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("LightRAG marked document as failed", report)
            self.assertIn("failed.txt", report)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    async def test_load_from_enriched_falls_back_for_partial_cards(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "partial_enriched_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched"
            normalized_dir = temp_root / "output" / "normalized"
            card_dir = enriched_dir / "topic"
            norm_dir = normalized_dir / "topic"
            card_dir.mkdir(parents=True, exist_ok=True)
            norm_dir.mkdir(parents=True, exist_ok=True)

            txt_path = norm_dir / "1.txt"
            txt_path.write_text(
                "[Канал: topic | Дата: 2026-04-30 12:00 | Пост: https://t.me/example/1]\n\n"
                "AfD выступает против помощи Украине и призывает к переговорам.",
                encoding="utf-8",
            )
            card = {
                "triage": "keep",
                "summary": "",
                "key_facts": [],
                "entities": {
                    "people": [],
                    "organizations": [],
                    "countries": [],
                    "locations": [],
                    "military_units": [],
                    "equipment": [],
                },
                "topics": [],
                "theses": [],
                "quotes": [],
                "events": [],
                "chunks": [],
                "visual": {"broll_notes": ""},
                "source_chain": {"original_source": "Some Source"},
                "provenance": {
                    "normalized_file": str(txt_path.relative_to(temp_root)),
                },
                "graph_text": (
                    "[Канал: topic | Дата: 2026-04-30 12:00 | Пост: https://t.me/example/1]\n\n"
                    "Источник: Some Source"
                ),
            }
            (card_dir / "1.enriched.json").write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )

            rag = _FakeRag()
            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", enriched_dir):
                    with patch.object(lightrag_loader.config, "NORMALIZED_DIR", normalized_dir):
                        with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", temp_root / "rag_storage"):
                            stats = await load_from_enriched(rag)

            self.assertEqual(stats["loaded"], 1)
            self.assertEqual(stats["fallback_normalized"], 1)
            self.assertEqual(rag.inserted[0]["texts"], [
                "AfD выступает против помощи Украине и призывает к переговорам."
            ])
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    async def test_load_from_enriched_falls_back_for_review_cards_with_text(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "review_enriched_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched"
            normalized_dir = temp_root / "output" / "normalized"
            card_dir = enriched_dir / "topic"
            norm_dir = normalized_dir / "topic"
            card_dir.mkdir(parents=True, exist_ok=True)
            norm_dir.mkdir(parents=True, exist_ok=True)

            txt_path = norm_dir / "1.txt"
            txt_path.write_text(
                "[Канал: topic | Дата: 2026-04-30 12:00 | Пост: https://t.me/example/1]\n\n"
                "На российском телевидении предлагают захватить Нарву.",
                encoding="utf-8",
            )
            card = {
                "triage": "review",
                "provenance": {"normalized_file": str(txt_path.relative_to(temp_root))},
                "graph_text": "",
            }
            (card_dir / "1.enriched.json").write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )

            rag = _FakeRag()
            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", enriched_dir):
                    with patch.object(lightrag_loader.config, "NORMALIZED_DIR", normalized_dir):
                        with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", temp_root / "rag_storage"):
                            stats = await load_from_enriched(rag)

            self.assertEqual(stats["loaded"], 1)
            self.assertEqual(stats["fallback_normalized"], 1)
            self.assertEqual(stats["skipped_triage"], 1)
            self.assertEqual(rag.inserted[0]["texts"], [
                "На российском телевидении предлагают захватить Нарву."
            ])
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    async def test_load_from_enriched_falls_back_for_missing_cards(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "missing_enriched_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched"
            normalized_dir = temp_root / "output" / "normalized"
            (enriched_dir / "topic").mkdir(parents=True, exist_ok=True)
            norm_dir = normalized_dir / "topic"
            norm_dir.mkdir(parents=True, exist_ok=True)

            txt_path = norm_dir / "1.txt"
            txt_path.write_text(
                "[Канал: topic | Дата: 2026-04-30 12:00 | Пост: https://t.me/example/1]\n\n"
                "Короткий, но важный тезис.",
                encoding="utf-8",
            )

            rag = _FakeRag()
            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", enriched_dir):
                    with patch.object(lightrag_loader.config, "NORMALIZED_DIR", normalized_dir):
                        with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", temp_root / "rag_storage"):
                            stats = await load_from_enriched(rag)

            self.assertEqual(stats["loaded"], 1)
            self.assertEqual(stats["fallback_normalized"], 1)
            self.assertEqual(stats["missing_enriched"], 1)
            self.assertEqual(rag.inserted[0]["texts"], ["Короткий, но важный тезис."])
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)


class QueryProfileTests(unittest.TestCase):
    def test_answer_profile_uses_top_k_15(self):
        profile = get_query_profile("answer")

        self.assertEqual(profile["top_k"], 15)

    def test_source_profile_uses_top_k_15(self):
        profile = get_query_profile("source")

        self.assertEqual(profile["top_k"], 15)

    def test_overview_profile_is_explicit_top_k_30(self):
        profile = get_query_profile("overview")

        self.assertEqual(profile["top_k"], 30)


class ShadowFallbackTests(unittest.IsolatedAsyncioTestCase):
    def test_shadow_fallback_matches_inflected_russian_terms(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "shadow_fallback_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched" / "Куба"
            normalized_dir = temp_root / "output" / "normalized" / "Куба"
            enriched_dir.mkdir(parents=True, exist_ok=True)
            normalized_dir.mkdir(parents=True, exist_ok=True)

            source_path = normalized_dir / "8.txt"
            source_path.write_text("США провели переговоры с Кубой в Гаване.", encoding="utf-8")
            card = {
                "triage": "keep",
                "summary": "США провели тайные переговоры с Кубой в Гаване.",
                "key_facts": [{"text": "Это первые прямые переговоры США и Кубы за 10 лет."}],
                "provenance": {"normalized_file": str(source_path.relative_to(temp_root))},
                "search_text": "США провели переговоры с Кубой в Гаване.",
            }
            (enriched_dir / "8.enriched.json").write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", temp_root / "output" / "enriched"):
                    result = _shadow_fallback_result(
                        "Что в базе говорится о Кубе и переговорах с США?",
                        "answer",
                    )

            self.assertIsNotNone(result)
            answer = result["llm_response"]["content"]
            self.assertIn("Куб", answer)
            self.assertIn("переговор", answer)
            self.assertIn("8.txt", answer)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def test_shadow_fallback_keeps_results_in_top_topic(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "shadow_topic_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            cuba_enriched = temp_root / "output" / "enriched" / "Cuba"
            cuba_normalized = temp_root / "output" / "normalized" / "Cuba"
            other_enriched = temp_root / "output" / "enriched" / "Other"
            other_normalized = temp_root / "output" / "normalized" / "Other"
            for directory in (cuba_enriched, cuba_normalized, other_enriched, other_normalized):
                directory.mkdir(parents=True, exist_ok=True)

            cuba_source = cuba_normalized / "5.txt"
            cuba_source.write_text("Cuba protests followed an economic crisis.", encoding="utf-8")
            other_source = other_normalized / "20.txt"
            other_source.write_text("Ultraright protests happened elsewhere.", encoding="utf-8")

            cuba_card = {
                "triage": "keep",
                "summary": "Cuba protests followed an economic crisis.",
                "key_facts": [{"text": "The relevant item is about protests in Cuba."}],
                "provenance": {"normalized_file": str(cuba_source.relative_to(temp_root))},
                "search_text": "Cuba protests economic crisis",
            }
            other_card = {
                "triage": "keep",
                "summary": "Ultraright protests happened elsewhere.",
                "key_facts": [{"text": "This card is not about Cuba."}],
                "provenance": {"normalized_file": str(other_source.relative_to(temp_root))},
                "search_text": "ultraright protests protests protests",
            }
            (cuba_enriched / "5.enriched.json").write_text(
                json.dumps(cuba_card, ensure_ascii=False),
                encoding="utf-8",
            )
            (other_enriched / "20.enriched.json").write_text(
                json.dumps(other_card, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", temp_root / "output" / "enriched"):
                    result = _shadow_fallback_result("Cuba protests", "answer")

            self.assertIsNotNone(result)
            answer = result["llm_response"]["content"]
            self.assertIn("Cuba", answer)
            self.assertIn("5.txt", answer)
            self.assertNotIn("ultraright", answer.casefold())
            self.assertNotIn("20.txt", answer)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def test_shadow_fallback_hides_visual_notes_for_regular_questions(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "shadow_visual_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched" / "Slovakia"
            normalized_dir = temp_root / "output" / "normalized" / "Slovakia"
            enriched_dir.mkdir(parents=True, exist_ok=True)
            normalized_dir.mkdir(parents=True, exist_ok=True)

            source_path = normalized_dir / "7.txt"
            source_path.write_text("Фицо стремится посетить Москву.", encoding="utf-8")
            card = {
                "triage": "keep",
                "summary": "Фицо стремится посетить Москву на фоне политического кризиса.",
                "key_facts": [{"text": "Страны Балтии отказали самолёту Фицо в пролёте."}],
                "visual": {
                    "broll_potential": "high",
                    "broll_notes": "Самолёт Фицо на фоне карты Европы.",
                },
                "provenance": {"normalized_file": str(source_path.relative_to(temp_root))},
                "search_text": "Фицо Москва политический кризис самолёт карта Европы",
            }
            (enriched_dir / "7.enriched.json").write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", temp_root / "output" / "enriched"):
                    result = _shadow_fallback_result(
                        "Что в базе говорится о Фицо и политическом кризисе?",
                        "answer",
                    )

            self.assertIsNotNone(result)
            answer = result["llm_response"]["content"]
            self.assertIn("Фицо", answer)
            self.assertNotIn("B-roll", answer)
            self.assertNotIn("Самолёт Фицо на фоне карты Европы", answer)
            self.assertNotIn("LightRAG не поднял", answer)
            self.assertNotIn("Точный поиск по карточкам", answer)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def test_shadow_fallback_includes_visual_notes_for_visual_questions(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "shadow_visual_requested_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched" / "Baltic"
            normalized_dir = temp_root / "output" / "normalized" / "Baltic"
            enriched_dir.mkdir(parents=True, exist_ok=True)
            normalized_dir.mkdir(parents=True, exist_ok=True)

            source_path = normalized_dir / "2.txt"
            source_path.write_text("Нарва и Эстония фигурируют в сценарии давления.", encoding="utf-8")
            card = {
                "triage": "keep",
                "summary": "Нарва упоминается в контексте давления на Эстонию.",
                "key_facts": [{"text": "Ида-Вирумаа и Нарва выделяются как чувствительные регионы."}],
                "visual": {
                    "broll_potential": "high",
                    "broll_notes": "Карта Эстонии с выделением Нарвы.",
                },
                "provenance": {"normalized_file": str(source_path.relative_to(temp_root))},
                "search_text": "Нарва Эстония визуалы карта",
            }
            (enriched_dir / "2.enriched.json").write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", temp_root / "output" / "enriched"):
                    result = _shadow_fallback_result(
                        "Какие кадры или визуалы можно использовать для ролика про Нарву и Эстонию?",
                        "answer",
                    )

            self.assertIsNotNone(result)
            answer = result["llm_response"]["content"]
            self.assertIn("Карта Эстонии", answer)
            self.assertIn("Нарв", answer)
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def test_card_context_for_query_returns_card_references(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "hybrid_card_context_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            enriched_dir = temp_root / "output" / "enriched" / "Hungary"
            normalized_dir = temp_root / "output" / "normalized" / "Hungary"
            enriched_dir.mkdir(parents=True, exist_ok=True)
            normalized_dir.mkdir(parents=True, exist_ok=True)

            source_path = normalized_dir / "148.txt"
            source_path.write_text("Trump supported Orban in Hungary.", encoding="utf-8")
            card = {
                "triage": "keep",
                "summary": "Trump publicly supported Orban before Hungarian elections.",
                "key_facts": [{"text": "The post frames this as explicit political support."}],
                "provenance": {"normalized_file": str(source_path.relative_to(temp_root))},
                "search_text": "Trump Orban Hungary explicit political support election",
            }
            (enriched_dir / "148.enriched.json").write_text(
                json.dumps(card, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", temp_root):
                with patch.object(lightrag_loader.config, "ENRICHED_DIR", temp_root / "output" / "enriched"):
                    with patch.object(lightrag_loader.config, "HYBRID_QUERY_CARDS_ENABLED", True):
                        context = _card_context_for_query("Trump Orban Hungary", "answer")

            self.assertIsNotNone(context)
            self.assertEqual(context["references"][0]["reference_id"], "card-1")
            self.assertIn("148.txt", context["references"][0]["file_path"])
            self.assertIn("explicit political support", "\n".join(context["shadow_context"][0]["facts"]))
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def test_attach_card_context_merges_references_without_duplicates(self):
        result = {
            "response": "Answer",
            "llm_response": {"content": "Answer"},
            "data": {"references": [{"reference_id": "1", "file_path": "D:/topic/1.txt"}]},
        }
        card_context = {
            "references": [
                {"reference_id": "card-1", "file_path": "D:/topic/1.txt"},
                {"reference_id": "card-2", "file_path": "D:/topic/2.txt"},
            ],
            "shadow_context": [{"reference_id": "card-2", "file_path": "D:/topic/2.txt", "facts": ["Fact"]}],
        }

        fixed = _attach_card_context(result, card_context)

        self.assertEqual(len(fixed["data"]["references"]), 2)
        self.assertEqual(fixed["data"]["references"][1]["reference_id"], "card-2")
        self.assertEqual(fixed["data"]["shadow_context"], card_context["shadow_context"])

    async def test_hybrid_synthesis_can_attach_context_without_second_llm(self):
        result = {
            "response": "Graph answer",
            "llm_response": {"content": "Graph answer"},
            "data": {"references": []},
        }
        card_context = {
            "references": [{"reference_id": "card-1", "file_path": "D:/topic/1.txt"}],
            "shadow_context": [{"reference_id": "card-1", "file_path": "D:/topic/1.txt", "facts": ["Card fact"]}],
        }

        with patch.object(lightrag_loader.config, "HYBRID_SYNTH_ENABLED", False):
            fixed = await _synthesize_hybrid_result("Question", "answer", result, card_context)

        self.assertEqual(fixed["llm_response"]["content"], "Graph answer")
        self.assertEqual(fixed["data"]["references"][0]["reference_id"], "card-1")

    async def test_query_rag_result_hybridizes_normal_lightrag_answer(self):
        class FakeQueryRag:
            async def aquery_llm(self, *args, **kwargs):
                return {
                    "response": "Graph answer about Orban.",
                    "llm_response": {"content": "Graph answer about Orban."},
                    "data": {"references": []},
                }

        card_context = {
            "references": [{"reference_id": "card-1", "file_path": "D:/topic/148.txt"}],
            "shadow_context": [{"reference_id": "card-1", "file_path": "D:/topic/148.txt", "facts": ["Card fact"]}],
        }

        async def fake_synth(question, query_profile, result, context):
            fixed = _attach_card_context(result, context)
            fixed["response"] = "Hybrid answer"
            fixed["llm_response"] = {"content": "Hybrid answer"}
            fixed["hybrid_context"] = "cards"
            return fixed

        with patch.object(lightrag_loader, "_card_context_for_query", return_value=card_context):
            with patch.object(lightrag_loader, "_synthesize_hybrid_result", side_effect=fake_synth):
                result = await lightrag_loader.query_rag_result(
                    FakeQueryRag(),
                    "Что в базе говорится про Трампа и Орбана?",
                    mode="hybrid",
                    query_profile="answer",
                )

        self.assertEqual(result["llm_response"]["content"], "Hybrid answer")
        self.assertEqual(result["hybrid_context"], "cards")
        self.assertEqual(result["data"]["references"][0]["reference_id"], "card-1")

    async def test_query_rag_result_uses_shadow_fallback_on_lightrag_error(self):
        class FailingQueryRag:
            async def aquery_llm(self, *args, **kwargs):
                raise RuntimeError("degraded endpoint")

        fallback = {
            "response": "Card fallback answer",
            "llm_response": {"content": "Card fallback answer"},
            "data": {"references": [{"reference_id": "card-1", "file_path": "D:/topic/1.txt"}]},
            "fallback": "shadow_search",
        }

        with patch.object(lightrag_loader, "_shadow_fallback_result", return_value=fallback):
            with patch.object(lightrag_loader.config, "HYBRID_SYNTH_ENABLED", False):
                result = await lightrag_loader.query_rag_result(
                    FailingQueryRag(),
                    "Что в базе говорится про Трампа и Орбана?",
                    mode="hybrid",
                    query_profile="answer",
                )

        self.assertEqual(result["llm_response"]["content"], "Card fallback answer")
        self.assertEqual(result["fallback"], "shadow_search")


class AnswerPostprocessTests(unittest.TestCase):
    def test_postprocess_uses_explicit_absent_word_for_unanswered_funding_questions(self):
        answer = _postprocess_answer_text(
            "В контексте не указано, кто напрямую финансирует AfD.",
            "Кто финансирует AfD?",
            "answer",
        )

        self.assertIn("отсутств", answer.casefold())
        self.assertIn("нельзя определить", answer.casefold())

    def test_postprocess_compacts_ultra_prefix_spelling(self):
        answer = _postprocess_answer_text(
            "Тезис про ультра-левых и ультра-правых дан в источнике.",
            "Откуда тезис про ультралевых и ультраправых?",
            "source",
        )

        self.assertIn("ультралев", answer.casefold())
        self.assertIn("ультраправ", answer.casefold())
        self.assertNotIn("ультра-лев", answer.casefold())

    def test_answer_looks_corrupt_detects_model_garbage(self):
        self.assertTrue(
            _answer_looks_corrupt(
                "контекстеmalloc успешного применения qqball ин‌م저 поддержки"
            )
        )
        self.assertFalse(
            _answer_looks_corrupt(
                "В базе говорится, что европейские ультраправые связаны с Трампом риторически."
            )
        )


class ExtractionPostprocessTests(unittest.TestCase):
    def test_postprocess_drops_relations_that_reference_missing_entities(self):
        tuple_delimiter = lightrag_loader.PROMPTS["DEFAULT_TUPLE_DELIMITER"]
        completion_delimiter = lightrag_loader.PROMPTS["DEFAULT_COMPLETION_DELIMITER"]
        raw = "\n".join(
            [
                f"entity{tuple_delimiter}Alice Weidel{tuple_delimiter}person{tuple_delimiter}Leader of AfD.",
                f"relation{tuple_delimiter}Alice Weidel{tuple_delimiter}Western states{tuple_delimiter}criticizes{tuple_delimiter}Alice Weidel criticizes Western states.",
                completion_delimiter,
            ]
        )

        cleaned = _postprocess_extraction_response(raw)

        self.assertIn("Alice Weidel", cleaned)
        self.assertNotIn("Western states", cleaned)
        self.assertNotIn("relation", cleaned)

    def test_postprocess_sanitizes_delimiters_inside_fields(self):
        tuple_delimiter = lightrag_loader.PROMPTS["DEFAULT_TUPLE_DELIMITER"]
        completion_delimiter = lightrag_loader.PROMPTS["DEFAULT_COMPLETION_DELIMITER"]
        raw = "\n".join(
            [
                f"entity{tuple_delimiter}Western states{tuple_delimiter}other{tuple_delimiter}Led by Great Britain {tuple_delimiter} and opposing peace.",
                completion_delimiter,
            ]
        )

        cleaned = _postprocess_extraction_response(raw)

        self.assertIn("Western states", cleaned)
        self.assertIn("Led by Great Britain and opposing peace.", cleaned)
        self.assertEqual(cleaned.count(tuple_delimiter), 3)


class RebuildStorageTests(unittest.TestCase):
    def test_rebuild_rag_storage_moves_existing_files_to_backup_and_recreates_dir(self):
        temp_root = Path(__file__).parent / ".tmp-tests" / "rebuild_rag_storage_case"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        try:
            root = temp_root
            storage_dir = root / "rag_storage"
            storage_dir.mkdir()
            original_file = storage_dir / "data.json"
            original_file.write_text("hello", encoding="utf-8")

            with patch.object(lightrag_loader.config, "PROJECT_ROOT", root):
                with patch.object(lightrag_loader.config, "RAG_STORAGE_DIR", storage_dir):
                    backup_path = lightrag_loader.rebuild_rag_storage()

            self.assertIsNotNone(backup_path)
            self.assertTrue(backup_path.exists())
            self.assertTrue((backup_path / "data.json").exists())
            self.assertTrue(storage_dir.exists())
            self.assertEqual(list(storage_dir.iterdir()), [])
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)


class SafeEntityMergePlanTests(unittest.TestCase):
    def test_plan_safe_entity_merges_handles_case_only_duplicates(self):
        plans = lightrag_loader.plan_safe_entity_merges(["HAMAS", "Hamas", "Russia"])

        self.assertEqual(plans, [{"target": "Hamas", "sources": ["HAMAS"]}])

    def test_plan_safe_entity_merges_uses_explicit_alias_map(self):
        plans = lightrag_loader.plan_safe_entity_merges(["USA", "United States", "Russia"])

        self.assertEqual(plans, [{"target": "United States", "sources": ["USA"]}])
