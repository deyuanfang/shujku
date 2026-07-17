"""Change Detection Engine — compares document versions and calculates severity."""

import json
import uuid
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.nlp_pipeline import nlp_pipeline

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def detect_changes(old_text: str, new_text: str, old_keywords: list[str] | None = None) -> dict:
    """Compare two versions of a document and calculate change severity.

    Args:
        old_text: The previous version's text content.
        new_text: The new version's text content.
        old_keywords: Previously extracted keywords (optional).

    Returns:
        Dict with: similarity, structural_similarity, entity_change_ratio,
                   severity_score, severity_label, diff_summary
    """
    if not old_text or not new_text:
        return {
            "similarity": 0.0,
            "severity_score": 1.0,
            "severity_label": "major",
            "diff_summary": "内容为空，无法比较",
        }

    # ── Metric A: Content Similarity (weight 0.40) ──
    content_similarity = _compute_content_similarity(old_text, new_text)
    content_drift = 1.0 - content_similarity

    # ── Metric B: Structural Similarity (weight 0.25) ──
    structural_similarity = _compute_structural_similarity(old_text, new_text)
    structural_drift = 1.0 - structural_similarity

    # ── Metric C: Keyword / Entity Change (weight 0.25) ──
    old_kw = set(old_keywords or nlp_pipeline.extract_keywords(old_text, top_n=15))
    new_kw = set(nlp_pipeline.extract_keywords(new_text, top_n=15))
    kw_jaccard = len(old_kw & new_kw) / max(1, len(old_kw | new_kw))
    entity_change = 1.0 - kw_jaccard

    # ── Metric D: Length Ratio Deviation (weight 0.10) ──
    old_len, new_len = len(old_text), len(new_text)
    length_ratio = min(old_len, new_len) / max(1, max(old_len, new_len))
    length_deviation = 1.0 - length_ratio

    # ── Weighted Severity Score ──
    severity = (
        0.40 * content_drift
        + 0.25 * structural_drift
        + 0.25 * entity_change
        + 0.10 * length_deviation
    )
    severity = max(0.0, min(1.0, severity))

    # Bump rule: if any single metric > 0.70, bump up one level
    max_metric = max(content_drift, structural_drift, entity_change)
    if max_metric > 0.70:
        severity = min(1.0, severity + 0.15)

    # ── Severity Label ──
    if severity < 0.10:
        label = "minor"
    elif severity < 0.30:
        label = "moderate"
    elif severity < 0.50:
        label = "significant"
    else:
        label = "major"

    # ── Diff Summary ──
    diff_parts = []
    if content_drift > 0.15:
        diff_parts.append(f"内容相似度: {content_similarity:.0%}")
    if structural_drift > 0.10:
        diff_parts.append(f"结构变化较大")
    if entity_change > 0.20:
        added = new_kw - old_kw
        removed = old_kw - new_kw
        if added:
            diff_parts.append(f"新增关键词: {', '.join(list(added)[:5])}")
        if removed:
            diff_parts.append(f"移除关键词: {', '.join(list(removed)[:5])}")

    # Generate a human-readable diff snippet
    diff_snippet = _generate_diff_snippet(old_text, new_text)

    return {
        "content_similarity": round(content_similarity, 4),
        "structural_similarity": round(structural_similarity, 4),
        "keyword_jaccard": round(kw_jaccard, 4),
        "entity_change_ratio": round(entity_change, 4),
        "length_deviation": round(length_deviation, 4),
        "severity_score": round(severity, 4),
        "severity_label": label,
        "diff_summary": "；".join(diff_parts) if diff_parts else "内容变化较小",
        "diff_snippet": diff_snippet,
        "added_keywords": list(new_kw - old_kw)[:10],
        "removed_keywords": list(old_kw - new_kw)[:10],
        "new_keywords": list(new_kw)[:15],
        "old_keywords": list(old_kw)[:15],
    }


def _compute_content_similarity(text1: str, text2: str) -> float:
    """Compute TF-IDF cosine similarity between two texts."""
    try:
        vectorizer = TfidfVectorizer(
            tokenizer=lambda t: nlp_pipeline.segment(t),
            token_pattern=None,
            max_features=500,
        )
        tfidf = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return float(similarity)
    except Exception:
        # Fallback to SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()


def _compute_structural_similarity(text1: str, text2: str) -> float:
    """Compare document structure by extracting headings/outline."""
    def extract_outline(text: str) -> list[str]:
        lines = text.split("\n")
        outline = []
        for line in lines:
            stripped = line.strip()
            # Markdown headings
            if stripped.startswith("#"):
                outline.append(stripped)
            # Lines that look like section titles
            elif len(stripped) < 60 and (
                stripped.endswith("：")
                or stripped.endswith(":")
                or (stripped.isascii() and len(stripped.split()) <= 8)
            ):
                outline.append(stripped)
        return outline

    outline1 = extract_outline(text1)
    outline2 = extract_outline(text2)

    if not outline1 and not outline2:
        return 1.0  # Neither has structure, consider similar
    if not outline1 or not outline2:
        return 0.0  # One has structure, other doesn't

    return SequenceMatcher(None, "\n".join(outline1), "\n".join(outline2)).ratio()


def _generate_diff_snippet(old_text: str, new_text: str, context_lines: int = 2) -> str:
    """Generate a human-readable diff of the most significant changes."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    matcher = SequenceMatcher(None, old_lines, new_lines)
    diffs = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            diffs.append(f"修改 {i1+1}-{i2} 行: ")
            diffs.append(f"  旧: {' '.join(old_lines[i1:i2])[:100]}")
            diffs.append(f"  新: {' '.join(new_lines[j1:j2])[:100]}")
        elif tag == "delete":
            diffs.append(f"删除 {i1+1}-{i2} 行")
        elif tag == "insert":
            diffs.append(f"新增 {j1+1}-{j2} 行")

    return "\n".join(diffs[:15])  # Limit diff size
