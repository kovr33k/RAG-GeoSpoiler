"""
Enricher Module — transforms normalized posts into structured memory cards.

Pipeline: normalized/ → enricher → enriched/ → LightRAG graph

Each normalized post gets an enriched JSON card containing:
- summary, key_facts, entities, topics, theses, quotes
- content_type classification and triage status
- graph_text (clean text for LightRAG) and search_text (broad text for search)
- provenance links back to normalized source and Telegram post
"""
