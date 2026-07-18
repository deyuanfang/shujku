"""Dynamic Category Manager — AI-powered auto-categorization that creates branches.

When a new document is uploaded, the AI analyzes content and:
1. Suggests the best category (existing or new)
2. If new, creates the category automatically
3. Suggests sub-categories for deep branching
4. Re-organizes the tree when a category grows too large
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.models import Category, Document
from app.services.ai_provider import get_provider
from app.services.nlp_pipeline import nlp_pipeline

logger = logging.getLogger(__name__)

CATEGORY_COLORS = [
    "#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6",
    "#8b5cf6", "#ef4444", "#06b6d4", "#84cc16", "#f97316",
    "#14b8a6", "#d946ef", "#f43f5e", "#0ea5e9", "#a855f7",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def auto_categorize_document(
    db: AsyncSession,
    document_id: str,
    content: str,
    title: str,
) -> dict:
    """AI analyzes document content and auto-assigns/creates categories.

    Returns:
        dict with primary_category, secondary_categories, new_categories_created
    """
    provider = get_provider()

    # Get existing categories
    result = await db.execute(select(Category).order_by(Category.document_count.desc()))
    existing_cats = result.scalars().all()

    cat_names = [c.name for c in existing_cats]
    cat_info = "\n".join([
        f"- {c.name} ({c.document_count}篇)" + (f" 子分类: {c.parent_id}" if c.parent_id else "")
        for c in existing_cats[:20]
    ])

    # ── Local NLP first ────────────────────────────
    keywords = nlp_pipeline.extract_keywords(content, top_n=15)
    keyword_str = ", ".join(keywords)

    # ── AI deep analysis ───────────────────────────
    new_cats_created = []
    primary_cat_id = None
    secondary_cat_ids = []

    if provider and await provider.is_available():
        try:
            prompt = f"""分析以下文档内容，建议最佳分类方案。

【文档标题】{title}
【文档内容】{content[:2000]}
【提取关键词】{keyword_str}

【现有分类】
{cat_info if cat_info else '(暂无分类)'}

请以 JSON 返回：
{{
  "primary_category": "最匹配的分类名（如无匹配，建议新分类名）",
  "is_new_primary": true/false,
  "new_category_color": "#hex颜色",
  "secondary_categories": ["副分类1", "副分类2"],
  "sub_category": "子分类名（可选，用于细化分支）",
  "confidence": 0.0-1.0,
  "reasoning": "分类理由"
}}"""

            response = await provider.chat(
                messages=[
                    {"role": "system", "content": "你是专业的知识分类专家。分析内容并建议最合适的分类方案。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400, temperature=0.3, json_mode=True,
            )

            # Parse response
            text = response.text.strip()
            if text.startswith("```"): text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                analysis = json.loads(text)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\{.*\}', text, re.DOTALL)
                analysis = json.loads(match.group()) if match else {}

            if not analysis:
                return await _local_fallback(db, keywords, cat_names)

            primary_name = analysis.get("primary_category", "").strip()

            # Find or create primary category
            if primary_name:
                cat_result = await db.execute(
                    select(Category).where(Category.name == primary_name)
                )
                existing = cat_result.scalar_one_or_none()
                if existing:
                    primary_cat_id = existing.id
                elif analysis.get("is_new_primary") or primary_name not in cat_names:
                    color = analysis.get("new_category_color") or CATEGORY_COLORS[len(existing_cats) % len(CATEGORY_COLORS)]
                    new_cat = Category(
                        id=str(uuid.uuid4()), name=primary_name,
                        description=f"AI自动创建: {analysis.get('reasoning', '')[:100]}",
                        color=color, document_count=0, sort_order=len(existing_cats),
                        created_at=_now(), updated_at=_now(),
                    )
                    db.add(new_cat)
                    await db.flush()
                    primary_cat_id = new_cat.id
                    new_cats_created.append({"id": new_cat.id, "name": primary_name, "color": color})
                    logger.info(f"Auto-created category: {primary_name}")

            # Handle secondary categories
            for sec_name in analysis.get("secondary_categories", [])[:3]:
                sec_name = sec_name.strip()
                if not sec_name or sec_name == primary_name:
                    continue
                cat_result = await db.execute(select(Category).where(Category.name == sec_name))
                existing = cat_result.scalar_one_or_none()
                if existing:
                    secondary_cat_ids.append(existing.id)
                elif sec_name not in cat_names:
                    color = CATEGORY_COLORS[(len(existing_cats) + len(new_cats_created)) % len(CATEGORY_COLORS)]
                    new_cat = Category(
                        id=str(uuid.uuid4()), name=sec_name,
                        color=color, document_count=0,
                        sort_order=len(existing_cats) + len(new_cats_created),
                        created_at=_now(), updated_at=_now(),
                    )
                    db.add(new_cat)
                    await db.flush()
                    secondary_cat_ids.append(new_cat.id)
                    new_cats_created.append({"id": new_cat.id, "name": sec_name, "color": color})

            # Handle sub-category
            sub_name = analysis.get("sub_category", "").strip()
            if sub_name and primary_cat_id:
                sub_result = await db.execute(select(Category).where(Category.name == sub_name))
                if not sub_result.scalar_one_or_none():
                    color = CATEGORY_COLORS[(len(existing_cats) + len(new_cats_created)) % len(CATEGORY_COLORS)]
                    new_sub = Category(
                        id=str(uuid.uuid4()), name=sub_name,
                        parent_id=primary_cat_id, color=color, document_count=0,
                        sort_order=0, created_at=_now(), updated_at=_now(),
                    )
                    db.add(new_sub)
                    await db.flush()
                    new_cats_created.append({"id": new_sub.id, "name": sub_name, "parent_id": primary_cat_id, "color": color})

            await db.flush()
            return {
                "primary_category_id": primary_cat_id,
                "primary_category_name": primary_name,
                "secondary_category_ids": secondary_cat_ids,
                "new_categories_created": new_cats_created,
                "confidence": analysis.get("confidence", 0.5),
                "reasoning": analysis.get("reasoning", ""),
                "source": "ai",
            }

        except Exception as e:
            logger.error(f"AI categorization failed: {e}")

    # Fallback to local NLP
    return await _local_fallback(db, keywords, cat_names)


async def _local_fallback(db: AsyncSession, keywords: list[str], cat_names: list[str]) -> dict:
    """Local NLP fallback for categorization."""
    primary_cat_id = None
    primary_name = "未分类"
    new_cats = []

    # Simple keyword-based matching
    if keywords:
        best_match = None
        best_score = 0
        for cat_name in cat_names:
            score = sum(1 for kw in keywords if kw in cat_name or cat_name in kw)
            if score > best_score:
                best_score = score
                best_match = cat_name

        if best_match and best_score >= 1:
            primary_name = best_match
            cat_result = await db.execute(select(Category).where(Category.name == best_match))
            if (existing := cat_result.scalar_one_or_none()):
                primary_cat_id = existing.id

    return {
        "primary_category_id": primary_cat_id,
        "primary_category_name": primary_name,
        "secondary_category_ids": [],
        "new_categories_created": new_cats,
        "confidence": 0.3,
        "source": "local",
    }
