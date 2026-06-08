"""
Reviewer Web UI — Streamlit-based interface for reviewing pending items.

Launch:
    streamlit run reviewer_app.py

Or automatically via:
    python main.py review --web
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# Add project root to path so config can be imported
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from normalizer.review_queue import (  # noqa: E402
    REVIEW_TYPE_AI_CHAT,
    REVIEW_TYPE_EXTERNAL_LINK,
    REVIEW_TYPE_UNINFORMATIVE,
    get_pending_reviews,
    mark_reviewed,
)

# ──────────────────────── Page Config ────────────────────────

st.set_page_config(
    page_title="GeoSpoiler Reviewer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────── Custom CSS ────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        color: white;
    }
    .main-header h1 {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        color: white;
    }
    .main-header p {
        font-size: 0.95rem;
        color: rgba(255,255,255,0.7);
        margin: 0.5rem 0 0 0;
    }

    /* Stats bar */
    .stats-bar {
        display: flex;
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #1e1e3f, #2a2a5a);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        flex: 1;
        text-align: center;
    }
    .stat-card .number {
        font-size: 2rem;
        font-weight: 700;
        color: #e94560;
    }
    .stat-card .label {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.5);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Review card */
    .review-card {
        background: linear-gradient(135deg, #1e1e3f, #252550);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .review-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }

    /* Type badge */
    .type-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .type-ai-chat {
        background: rgba(155, 89, 182, 0.2);
        color: #bb86fc;
        border: 1px solid rgba(155, 89, 182, 0.3);
    }
    .type-external-link {
        background: rgba(52, 152, 219, 0.2);
        color: #64b5f6;
        border: 1px solid rgba(52, 152, 219, 0.3);
    }
    .type-uninformative {
        background: rgba(241, 196, 15, 0.2);
        color: #ffd54f;
        border: 1px solid rgba(241, 196, 15, 0.3);
    }

    /* Channel info */
    .channel-info {
        color: rgba(255,255,255,0.5);
        font-size: 0.85rem;
        margin: 0.5rem 0;
    }

    /* Message text preview */
    .message-preview {
        background: rgba(0,0,0,0.2);
        border-left: 3px solid #e94560;
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.75rem 0;
        font-size: 0.9rem;
        color: rgba(255,255,255,0.85);
        max-height: 200px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* URL display */
    .url-display {
        background: rgba(0,0,0,0.15);
        padding: 0.5rem 0.75rem;
        border-radius: 8px;
        font-family: monospace;
        font-size: 0.8rem;
        color: #64b5f6;
        word-break: break-all;
        margin: 0.5rem 0;
    }

    /* Reason text */
    .reason-text {
        color: rgba(255,255,255,0.4);
        font-size: 0.8rem;
        font-style: italic;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        color: rgba(255,255,255,0.4);
    }
    .empty-state .emoji {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    .empty-state h2 {
        font-size: 1.5rem;
        color: rgba(255,255,255,0.6);
        margin-bottom: 0.5rem;
    }

    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────── Helpers ────────────────────────

TYPE_BADGES = {
    REVIEW_TYPE_AI_CHAT: ("AI Диалог", "type-ai-chat"),
    REVIEW_TYPE_EXTERNAL_LINK: ("Внешняя ссылка", "type-external-link"),
    REVIEW_TYPE_UNINFORMATIVE: ("Малоинформативный", "type-uninformative"),
}


def _get_type_badge_html(review_type: str) -> str:
    label, css_class = TYPE_BADGES.get(review_type, ("Ревью", "type-external-link"))
    return f'<span class="type-badge {css_class}">{label}</span>'


def _load_all_items() -> list[dict]:
    """Load all review queue items (all statuses)."""
    items = []
    for f in config.REVIEW_QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_filepath"] = str(f)
            items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    # Sort: pending first, then by queued_at descending
    status_order = {"pending": 0, "processed": 1, "skipped": 2}
    items.sort(key=lambda x: (status_order.get(x.get("status", ""), 3), x.get("queued_at", "")))
    return items


def _save_override_text(item: dict, new_text: str) -> str | None:
    """Save override text to the normalized directory, replacing the original."""
    normalized_path = item.get("normalized_filepath")
    if not normalized_path:
        # Try to reconstruct the path from channel + message_id
        channel = item.get("channel", "unknown")
        msg_id = item.get("message_id", 0)
        sanitized_channel = "".join(
            c if c.isalnum() or c in " _-" else "_" for c in channel
        ).strip()
        normalized_path = str(config.NORMALIZED_DIR / sanitized_channel / f"{msg_id}.txt")

    path = Path(normalized_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    return str(path)


def _save_uploaded_image(item: dict, uploaded_file) -> str | None:
    """Save uploaded image next to the normalized file."""
    channel = item.get("channel", "unknown")
    msg_id = item.get("message_id", 0)
    sanitized_channel = "".join(
        c if c.isalnum() or c in " _-" else "_" for c in channel
    ).strip()

    img_dir = config.NORMALIZED_DIR / sanitized_channel
    img_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(uploaded_file.name).suffix or ".jpg"
    img_path = img_dir / f"{msg_id}_review_img{ext}"
    img_path.write_bytes(uploaded_file.getvalue())
    return str(img_path)


# ──────────────────────── Main UI ────────────────────────

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🔍 GeoSpoiler Reviewer</h1>
        <p>Просмотр и обработка элементов очереди ревью</p>
    </div>
    """, unsafe_allow_html=True)

    # Load items
    all_items = _load_all_items()
    pending = [i for i in all_items if i.get("status") == "pending"]
    processed = [i for i in all_items if i.get("status") == "processed"]
    skipped = [i for i in all_items if i.get("status") == "skipped"]

    # Stats bar
    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-card">
            <div class="number">{len(pending)}</div>
            <div class="label">Ожидают ревью</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(processed)}</div>
            <div class="label">Обработано</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(skipped)}</div>
            <div class="label">Пропущено</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(all_items)}</div>
            <div class="label">Всего</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Filter
    filter_options = ["Все ожидающие", "AI Диалоги", "Внешние ссылки", "Малоинформативные", "Обработанные"]
    selected_filter = st.selectbox("Фильтр:", filter_options, label_visibility="collapsed")

    if selected_filter == "Все ожидающие":
        display_items = pending
    elif selected_filter == "AI Диалоги":
        display_items = [i for i in pending if i.get("review_type") == REVIEW_TYPE_AI_CHAT]
    elif selected_filter == "Внешние ссылки":
        display_items = [i for i in pending if i.get("review_type") == REVIEW_TYPE_EXTERNAL_LINK]
    elif selected_filter == "Малоинформативные":
        display_items = [i for i in pending if i.get("review_type") == REVIEW_TYPE_UNINFORMATIVE]
    elif selected_filter == "Обработанные":
        display_items = processed + skipped
    else:
        display_items = pending

    # Empty state
    if not display_items:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">✅</div>
            <h2>Очередь пуста!</h2>
            <p>Нет элементов для ревью. Запустите пайплайн, чтобы появились новые элементы.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Render items
    for idx, item in enumerate(display_items):
        _render_review_card(item, idx)


def _render_review_card(item: dict, idx: int):
    """Render a single review card with action buttons."""
    review_type = item.get("review_type", "unknown")
    status = item.get("status", "pending")
    channel = item.get("channel", "?")
    msg_id = item.get("message_id", "?")
    url = item.get("url", "")
    reason = item.get("reason", "")
    message_text = item.get("message_text", "")
    message_date = item.get("message_date", "")
    filepath = item.get("_filepath", "")

    # Card header
    badge_html = _get_type_badge_html(review_type)
    status_emoji = "⏳" if status == "pending" else ("✅" if status == "processed" else "⏭️")

    # Build optional sections
    url_html = ""
    if url:
        url_html = f'<div class="url-display">🔗 {_escape_html(url)}</div>'

    reason_html = ""
    if reason:
        reason_html = f'<div class="reason-text">💡 {_escape_html(reason)}</div>'

    preview_html = ""
    if message_text:
        truncated = _escape_html(message_text[:500])
        if len(message_text) > 500:
            truncated += "..."
        preview_html = f'<div class="message-preview">{truncated}</div>'

    st.markdown(
        f'<div class="review-card">'
        f'{badge_html}'
        f'<span style="float: right; opacity: 0.5;">{status_emoji} {status}</span>'
        f'<div class="channel-info">'
        f'📌 {_escape_html(str(channel))} &nbsp;|&nbsp; 🆔 {msg_id} &nbsp;|&nbsp; 📅 {message_date or "?"}'
        f'</div>'
        f'{url_html}'
        f'{reason_html}'
        f'{preview_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Actions (only for pending items)
    if status == "pending":
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("⏭️ Пропустить", key=f"skip_{idx}", use_container_width=True):
                mark_reviewed(filepath, skip=True)
                st.rerun()

        with col2:
            if st.button("✅ Одобрить", key=f"approve_{idx}", use_container_width=True):
                mark_reviewed(filepath, extracted_text=message_text)
                st.rerun()

        with col3:
            if st.button("✏️ Редактировать", key=f"edit_{idx}", use_container_width=True):
                st.session_state[f"editing_{idx}"] = True

        # Edit mode
        if st.session_state.get(f"editing_{idx}", False):
            st.markdown("---")
            st.markdown("##### ✏️ Ваша версия текста")

            if url:
                if st.button("🕸️ Извлечь текст (Crawl4AI)", key=f"auto_{idx}"):
                    with st.spinner("Загрузка и парсинг сайта..."):
                        import asyncio
                        from normalizer.web_handler import extract_web_text
                        extracted = asyncio.run(extract_web_text(url))
                        st.session_state[f"text_{idx}"] = extracted
                        st.rerun()

            edited_text = st.text_area(
                "Текст:",
                value=st.session_state.get(f"text_{idx}", message_text or ""),
                height=200,
                key=f"text_{idx}",
                label_visibility="collapsed",
            )

            uploaded_image = st.file_uploader(
                "📎 Прикрепить изображение (необязательно):",
                type=["jpg", "jpeg", "png", "webp", "gif"],
                key=f"img_{idx}",
            )

            ecol1, ecol2 = st.columns(2)
            with ecol1:
                if st.button("💾 Сохранить", key=f"save_{idx}", use_container_width=True, type="primary"):
                    img_path = None
                    if uploaded_image:
                        img_path = _save_uploaded_image(item, uploaded_image)

                    # Save override text to normalized directory
                    if edited_text.strip():
                        _save_override_text(item, edited_text.strip())

                    mark_reviewed(
                        filepath,
                        extracted_text=edited_text.strip() if edited_text.strip() else None,
                        skip=not edited_text.strip(),
                        attached_image=img_path,
                    )
                    st.session_state[f"editing_{idx}"] = False
                    st.rerun()

            with ecol2:
                if st.button("❌ Отмена", key=f"cancel_{idx}", use_container_width=True):
                    st.session_state[f"editing_{idx}"] = False
                    st.rerun()

        st.markdown("")  # spacer


def _escape_html(text: str) -> str:
    """Basic HTML escaping for safe display."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br>")
    )


if __name__ == "__main__":
    main()
