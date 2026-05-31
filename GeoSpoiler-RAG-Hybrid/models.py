"""Pydantic data contracts for GeoSpoiler local artifacts.

These models are intentionally permissive at the edges: they describe the
current artifact shape, preserve unknown fields, and leave corpus-quality
warnings to the soft validation layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_CLAIM_TYPES = {"fact", "source_claim", "hypothesis"}


class ContractModel(BaseModel):
    """Base model that keeps forward-compatible fields."""

    model_config = ConfigDict(extra="allow")


class SourceId(ContractModel):
    value: str

    @classmethod
    def from_provenance(cls, provenance: "Provenance | dict[str, Any]") -> "SourceId | None":
        data = provenance.model_dump() if isinstance(provenance, BaseModel) else provenance
        existing = _clean_str(data.get("source_id"))
        if existing:
            return cls(value=existing)

        message_id = _clean_str(data.get("message_id"))
        if not message_id:
            return None

        channel_id = _clean_str(data.get("channel_id"))
        if channel_id:
            return cls(value=f"telegram:{channel_id}:{message_id}")

        channel_name = _clean_str(data.get("channel_name"))
        if channel_name:
            return cls(value=f"telegram:{channel_name}:{message_id}")

        return None


class ContentHash(ContractModel):
    value: str


class Provenance(ContractModel):
    channel_name: str = ""
    channel_id: int | str | None = None
    channel_username: str = ""
    message_id: int | str | None = None
    date: str = ""
    post_url: str = ""
    normalized_file: str = ""
    meta_file: str = ""
    is_forward: bool | None = None
    forward_from: str | None = None
    forward_from_name: str | None = None
    forward_from_id: int | str | None = None
    forward_date: str | None = None

    @property
    def source_id(self) -> SourceId | None:
        return SourceId.from_provenance(self)


class KeyFact(ContractModel):
    text: str
    claim_type: str = "fact"

    @field_validator("claim_type", mode="before")
    @classmethod
    def _normalize_claim_type(cls, value: Any) -> str:
        return _clean_str(value) or "fact"


class Reference(ContractModel):
    source_id: str = ""
    reference_type: str = ""
    url: str = ""
    label: str = ""
    origin: str = ""
    post_url: str = ""
    file_path: str = ""


class Entities(ContractModel):
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    military_units: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_entity_list(cls, value: Any) -> list[str]:
        return _string_list(value)


class Visual(ContractModel):
    has_images: bool = False
    has_video: bool = False
    video_type: str | None = None
    broll_potential: str = ""
    broll_notes: str = ""
    image_descriptions: list[Any] = Field(default_factory=list)


class SourceChain(ContractModel):
    original_source: str = ""
    cited_sources: list[Any] = Field(default_factory=list)
    youtube_url: str | None = None


class Dedup(ContractModel):
    is_duplicate: bool = False
    duplicate_group_id: str | None = None
    canonical_memory_id: str | None = None
    duplicate_reason: str | None = None


class EnrichedCard(ContractModel):
    version: int | str | None = None
    enriched_at: str = ""
    provenance: Provenance
    content_type: str = ""
    triage: str = ""
    triage_reason: str = ""
    language: str = ""
    summary: str = ""
    key_facts: list[KeyFact] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    topics: list[str] = Field(default_factory=list)
    theses: list[Any] = Field(default_factory=list)
    quotes: list[Any] = Field(default_factory=list)
    events: list[Any] = Field(default_factory=list)
    query_aliases: list[str] = Field(default_factory=list)
    visual: Visual = Field(default_factory=Visual)
    source_chain: SourceChain = Field(default_factory=SourceChain)
    chunks: list[Any] = Field(default_factory=list)
    noise: list[Any] = Field(default_factory=list)
    dedup: Dedup = Field(default_factory=Dedup)
    graph_text: str = ""
    search_text: str = ""

    @field_validator("topics", "query_aliases", mode="before")
    @classmethod
    def _coerce_string_list(cls, value: Any) -> list[str]:
        return _string_list(value)

    @property
    def source_id(self) -> SourceId | None:
        return self.provenance.source_id


class NormalizedMeta(ContractModel):
    channel_name: str = ""
    channel_id: int | str | None = None
    channel_username: str = ""
    message_id: int | str | None = None
    date: str = ""
    post_url: str = ""
    is_forward: bool = False
    forward_from_name: str | None = None
    forward_from_id: int | str | None = None
    forward_date: str | None = None
    has_text: bool = False
    has_images: bool = False
    image_count: int = 0
    has_video: bool = False
    has_voice: bool = False
    has_document: bool = False
    youtube_urls: list[str] = Field(default_factory=list)
    instagram_urls: list[str] = Field(default_factory=list)
    ai_chat_urls: list[str] = Field(default_factory=list)
    web_urls: list[str] = Field(default_factory=list)
    media: list[Any] = Field(default_factory=list)

    @field_validator("youtube_urls", "instagram_urls", "ai_chat_urls", "web_urls", mode="before")
    @classmethod
    def _coerce_url_list(cls, value: Any) -> list[str]:
        return _string_list(value)

    @property
    def source_id(self) -> SourceId | None:
        return SourceId.from_provenance(self.model_dump())


class WikiPageRef(ContractModel):
    page_path: str
    sources: list[str] = Field(default_factory=list)
    title: str = ""
    snippet: str = ""


class QueryProfile(ContractModel):
    name: Literal["answer", "source", "overview"]
    mode: str = "hybrid"
    wiki_enabled: bool = True
    hybrid_synth_enabled: bool = True


class ExperimentRun(ContractModel):
    run_id: str
    model: str
    provider: str = ""
    score: float | None = None
    passed: int | None = None
    total: int | None = None
    avg_duration_seconds: float | None = None
    cache_cleared: bool = False
    artifact_paths: list[Path] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_str(item) for item in value if _clean_str(item)]
    text = _clean_str(value)
    return [text] if text else []


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
