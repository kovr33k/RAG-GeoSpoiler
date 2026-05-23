"""
Normalizer Pipeline - orchestrates the conversion of TelegramMessage -> normalized .txt file.

Takes classified messages from the router and runs appropriate handlers,
then assembles everything into a single normalized text file per message.
"""

import logging
import json
from dataclasses import dataclass, field
from pathlib import Path

import config
from fetcher.telegram_client import TelegramMessage
from normalizer.router import ClassifiedMessage, classify
from normalizer.text_handler import normalize_text
from normalizer.youtube_handler import extract_youtube_text
from normalizer.web_handler import extract_web_text
from normalizer.instagram_handler import extract_instagram_text
from normalizer.image_handler import describe_image
from normalizer.ai_chat_handler import queue_for_review
from normalizer.translator import translate_to_russian_if_needed

logger = logging.getLogger("geospoiler.normalizer")


@dataclass
class NormalizedMessageResult:
    """Normalization result for a single Telegram message."""

    status: str  # normalized | skipped
    filepath: str | None = None
    text: str | None = None
    ai_review_created: int = 0
    ai_review_already_reviewed: int = 0


@dataclass
class NormalizationBatchResult:
    """Aggregated normalization output and content statistics for a batch."""

    texts_with_paths: list[tuple[str, str]] = field(default_factory=list)
    messages_total: int = 0
    messages_with_text: int = 0
    messages_with_images: int = 0
    images_total: int = 0
    messages_with_native_video: int = 0
    messages_with_youtube: int = 0
    youtube_links_total: int = 0
    messages_with_instagram_reels: int = 0
    instagram_reel_links_total: int = 0
    messages_with_instagram_posts: int = 0
    instagram_post_links_total: int = 0
    messages_with_ai_chat: int = 0
    ai_chat_links_total: int = 0
    messages_with_web: int = 0
    web_links_total: int = 0
    normalized_messages: int = 0
    skipped_messages: int = 0
    failed_messages: int = 0
    processed_messages: int = 0
    ai_review_created: int = 0
    ai_review_already_reviewed: int = 0

    def merge(self, other: "NormalizationBatchResult") -> None:
        """Merge another batch result into this one."""
        self.texts_with_paths.extend(other.texts_with_paths)
        self.messages_total += other.messages_total
        self.messages_with_text += other.messages_with_text
        self.messages_with_images += other.messages_with_images
        self.images_total += other.images_total
        self.messages_with_native_video += other.messages_with_native_video
        self.messages_with_youtube += other.messages_with_youtube
        self.youtube_links_total += other.youtube_links_total
        self.messages_with_instagram_reels += other.messages_with_instagram_reels
        self.instagram_reel_links_total += other.instagram_reel_links_total
        self.messages_with_instagram_posts += other.messages_with_instagram_posts
        self.instagram_post_links_total += other.instagram_post_links_total
        self.messages_with_ai_chat += other.messages_with_ai_chat
        self.ai_chat_links_total += other.ai_chat_links_total
        self.messages_with_web += other.messages_with_web
        self.web_links_total += other.web_links_total
        self.normalized_messages += other.normalized_messages
        self.skipped_messages += other.skipped_messages
        self.failed_messages += other.failed_messages
        self.processed_messages += other.processed_messages
        self.ai_review_created += other.ai_review_created
        self.ai_review_already_reviewed += other.ai_review_already_reviewed


def normalize_message(
    msg: TelegramMessage,
    classified: ClassifiedMessage | None = None,
) -> NormalizedMessageResult:
    """
    Normalize a single Telegram message into a text document.

    Returns normalization metadata and saves the file to
    output/normalized/{channel}/{msg_id}.txt when meaningful content exists.
    """
    classified = classified or classify(msg)

    sections = []
    ai_review_created = 0
    ai_review_already_reviewed = 0

    header = _build_header(msg)
    sections.append(header)

    if classified.has_text:
        clean_text = normalize_text(msg.text)
        text_without_urls = _strip_urls_from_text(clean_text, msg.urls)
        if text_without_urls.strip():
            sections.append(text_without_urls)

    for img_path in classified.image_paths:
        caption = msg.text if not classified.has_text else ""
        img_desc = describe_image(img_path, caption=caption)
        sections.append(img_desc)

    if classified.has_video:
        sections.append("[Видео: пост содержал видео - не обработано]")

    for url in classified.youtube_urls:
        yt_text = extract_youtube_text(url)
        sections.append(yt_text)

    for url in classified.instagram_urls:
        ig_text = extract_instagram_text(url)
        sections.append(ig_text)

    for url in classified.ai_chat_urls:
        review_result = queue_for_review(
            url=url,
            channel_name=msg.channel_name,
            message_id=msg.message_id,
            message_text=msg.text,
            message_date=msg.date,
        )
        sections.append(review_result.placeholder_text)
        if review_result.action == "queued":
            ai_review_created += 1
        elif review_result.action == "already_reviewed":
            ai_review_already_reviewed += 1

    for url in classified.web_urls:
        web_text = extract_web_text(url)
        sections.append(web_text)

    if len(sections) <= 1:
        logger.debug(f"  Message {msg.message_id} from '{msg.channel_name}' has no content - skipping.")
        return NormalizedMessageResult(status="skipped")

    # The header is sections[0]. We should not translate the header to avoid breaking metadata parsers.
    header = sections[0]
    body_text = "\n\n".join(sections[1:])
    translated_body = translate_to_russian_if_needed(body_text)
    
    full_text = f"{header}\n\n{translated_body}"
    metadata = _build_metadata(msg, classified)

    filepath = _save_normalized(msg, full_text, metadata)
    logger.info(f"  Normalized: {filepath.name} ({len(full_text)} chars)")

    return NormalizedMessageResult(
        status="normalized",
        filepath=str(filepath),
        text=full_text,
        ai_review_created=ai_review_created,
        ai_review_already_reviewed=ai_review_already_reviewed,
    )


def normalize_batch(messages: list[TelegramMessage]) -> NormalizationBatchResult:
    """
    Normalize a batch of messages.

    Returns normalized texts plus aggregate content/outcome statistics.
    """
    batch = NormalizationBatchResult()

    for msg in messages:
        classified = classify(msg)
        batch.messages_total += 1
        _accumulate_classification_stats(batch, classified)

        try:
            result = normalize_message(msg, classified=classified)
            batch.ai_review_created += result.ai_review_created
            batch.ai_review_already_reviewed += result.ai_review_already_reviewed

            if result.status == "normalized" and result.filepath and result.text is not None:
                batch.normalized_messages += 1
                batch.texts_with_paths.append((result.filepath, result.text))
            else:
                batch.skipped_messages += 1
        except Exception as e:
            batch.failed_messages += 1
            logger.error(
                f"  Error normalizing msg {msg.message_id} from '{msg.channel_name}': {e}",
                exc_info=True,
            )

    return batch


def _accumulate_classification_stats(
    batch: NormalizationBatchResult,
    classified: ClassifiedMessage,
) -> None:
    """Update aggregate counters from one classified message."""
    if classified.has_text:
        batch.messages_with_text += 1

    if classified.image_paths:
        batch.messages_with_images += 1
        batch.images_total += len(classified.image_paths)

    if classified.has_video:
        batch.messages_with_native_video += 1

    if classified.youtube_urls:
        batch.messages_with_youtube += 1
        batch.youtube_links_total += len(classified.youtube_urls)

    if classified.ai_chat_urls:
        batch.messages_with_ai_chat += 1
        batch.ai_chat_links_total += len(classified.ai_chat_urls)

    if classified.web_urls:
        batch.messages_with_web += 1
        batch.web_links_total += len(classified.web_urls)

    reel_links = 0
    post_links = 0
    for url in classified.instagram_urls:
        if "/reel/" in url.lower():
            reel_links += 1
        else:
            post_links += 1

    if reel_links:
        batch.messages_with_instagram_reels += 1
        batch.instagram_reel_links_total += reel_links

    if post_links:
        batch.messages_with_instagram_posts += 1
        batch.instagram_post_links_total += post_links


def _build_header(msg: TelegramMessage) -> str:
    """Build the metadata header line for a normalized document."""
    parts = [f"Канал: {msg.channel_name}"]

    if msg.is_forward and msg.forward_from_name:
        parts.append(f"Источник: {msg.forward_from_name} (пересылка)")

    date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "?"
    parts.append(f"Дата: {date_str}")
    parts.append(f"Пост: {msg.post_url}")

    return "[" + " | ".join(parts) + "]"


def _build_metadata(msg: TelegramMessage, classified: ClassifiedMessage) -> dict:
    """Build structured metadata saved alongside the normalized text."""
    return {
        "channel_name": msg.channel_name,
        "channel_id": msg.channel_id,
        "channel_username": msg.channel_username,
        "message_id": msg.message_id,
        "date": msg.date.isoformat() if msg.date else None,
        "post_url": msg.post_url,
        "is_forward": msg.is_forward,
        "forward_from_name": msg.forward_from_name,
        "forward_from_id": msg.forward_from_id,
        "forward_date": msg.forward_date.isoformat() if msg.forward_date else None,
        "has_text": classified.has_text,
        "has_images": bool(classified.image_paths),
        "image_count": len(classified.image_paths),
        "has_video": classified.has_video,
        "has_voice": msg.has_voice,
        "has_document": msg.has_document,
        "youtube_urls": classified.youtube_urls,
        "instagram_urls": classified.instagram_urls,
        "ai_chat_urls": classified.ai_chat_urls,
        "web_urls": classified.web_urls,
    }


def _strip_urls_from_text(text: str, urls: list[str]) -> str:
    """Remove URLs from text body (since they are expanded into separate sections)."""
    result = text
    for url in urls:
        result = result.replace(url, "")
    import re

    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _get_filepath(msg: TelegramMessage) -> Path:
    """Get the output filepath for a normalized message."""
    channel_dir = config.NORMALIZED_DIR / _sanitize(msg.channel_name)
    channel_dir.mkdir(parents=True, exist_ok=True)
    return channel_dir / f"{msg.message_id}.txt"


def _save_normalized(msg: TelegramMessage, text: str, metadata: dict | None = None) -> Path:
    """Save normalized text plus sidecar metadata to files."""
    filepath = _get_filepath(msg)
    filepath.write_text(text, encoding="utf-8")
    if metadata is not None:
        meta_path = filepath.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return filepath


def _sanitize(name: str) -> str:
    """Sanitize string for use as directory name."""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
