"""AI Data Organizer (数据整理大师) — automatically organizes knowledge after upload.

This agent runs after each new document is added and:
1. Classifies content into categories (creating new ones if needed)
2. Generates structured summaries with key points
3. Extracts entities and links them to existing knowledge
4. Detects relationships with existing documents
5. Proposes category reorganization when clusters emerge
6. Generates cross-category insights
"""

import json
import logging
from typing import Optional

from app.services.ai_provider import get_provider, AIResponse
from app.services.nlp_pipeline import nlp_pipeline

logger = logging.getLogger(__name__)

# System prompt for the Data Organizer persona
ORGANIZER_SYSTEM = """你是一个专业的知识整理大师（数据整理大师）。

你的职责是：
1. 精准分类：根据内容自动归类，必要时建议创建新分类
2. 结构化总结：对每篇内容生成3-5个关键要点的总结
3. 实体提取：识别文中的人名、组织、技术术语、概念、事件
4. 关系发现：找出新内容与知识库中已有内容的关联
5. 质量评估：对内容的重要性、完整性进行评分
6. 整理建议：当发现某分类下内容过多时，建议拆分；发现相关分类时，建议合并

你必须始终以 JSON 格式返回结果。保持专业、准确、有条理。"""


async def organize_new_document(
    title: str,
    content: str,
    existing_categories: list[dict],
    existing_entities: list[dict],
    recent_documents: list[dict],
) -> dict:
    """Run the full organization pipeline on a new document.

    Returns a structured dict with classification, summary, entities, relationships, and suggestions.
    """
    provider = get_provider()
    if not provider or not await provider.is_available():
        return _fallback_organize(title, content)

    # Truncate long content
    content_snippet = content[:4000] if len(content) > 4000 else content

    # Build context about existing knowledge
    cat_context = "\n".join([f"- {c['name']} ({c.get('document_count', 0)}篇)" for c in existing_categories[:15]])
    ent_context = "\n".join([f"- {e['name']} [{e.get('type', '')}]" for e in existing_entities[:20]])
    doc_context = "\n".join([f"- {d['title']}" for d in recent_documents[:10]])

    prompt = f"""请整理以下新文档：

【文档标题】{title}
【文档内容】
{content_snippet}

【知识库现有分类】
{cat_context or '(暂无分类)'}

【知识库已有实体】
{ent_context or '(暂无实体)'}

【最近文档】
{doc_context or '(暂无)'}

请返回 JSON：
{{
  "classification": {{
    "suggested_category": "最合适的分类名",
    "confidence": 0.0-1.0,
    "is_new_category": true/false,
    "new_category_description": "如果是新分类，描述其范围",
    "alternative_categories": ["备选分类1", "备选分类2"]
  }},
  "summary": {{
    "one_liner": "一句话总结",
    "key_points": ["要点1", "要点2", "要点3"],
    "target_audience": "适合什么人阅读",
    "difficulty": "beginner/intermediate/advanced"
  }},
  "entities": [
    {{"name": "实体名", "type": "person/organization/concept/technology/event/location", "description": "简短描述"}}
  ],
  "relationships": [
    {{"target_entity": "已有实体名", "relation": "关系描述", "strength": 0.0-1.0}}
  ],
  "quality": {{
    "importance": 0.0-1.0,
    "completeness": 0.0-1.0,
    "is_core_knowledge": true/false,
    "notes": "质量评估说明"
  }},
  "suggestions": {{
    "category_actions": ["建议1", "建议2"],
    "merge_suggestions": [{{"cat1": "分类A", "cat2": "分类B", "reason": "原因"}}]
  }}
}}

只返回 JSON，不要其他内容。"""

    try:
        response = await provider.chat(
            messages=[
                {"role": "system", "content": ORGANIZER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500, temperature=0.3, json_mode=True,
        )
        result = _parse_json_response(response.text)
        return result if result else _fallback_organize(title, content)
    except Exception as e:
        logger.error(f"Organizer error: {e}")
        return _fallback_organize(title, content)


async def review_categories(all_categories: list[dict]) -> dict:
    """Periodic review: suggest category reorganization."""
    provider = get_provider()
    if not provider or not await provider.is_available():
        return {"suggestions": []}

    cat_list = "\n".join([
        f"- {c['name']}: {c.get('document_count', 0)}篇, 子分类: {', '.join([s.get('name','') for s in c.get('children', [])])}"
        for c in all_categories[:30]
    ])

    prompt = f"""请审查知识库的分类体系并提出建议：

【当前分类】
{cat_list}

请以 JSON 格式返回：
{{
  "suggestions": {{
    "merges": [{{"categories": ["分类A", "分类B"], "new_name": "合并后名称", "reason": "原因"}}],
    "splits": [{{"category": "分类名", "into": ["子分类1", "子分类2"], "reason": "原因"}}],
    "renames": [{{"old": "旧名", "new": "新名", "reason": "原因"}}],
    "new_categories": [{{"name": "新分类", "description": "描述", "parent": "父分类"}}]
  }},
  "overall_health": "good/fair/poor",
  "health_notes": "整体评估说明"
}}"""

    try:
        response = await provider.chat(
            messages=[{"role": "system", "content": ORGANIZER_SYSTEM}, {"role": "user", "content": prompt}],
            max_tokens=800, temperature=0.3, json_mode=True,
        )
        return _parse_json_response(response.text) or {"suggestions": {}}
    except Exception as e:
        logger.error(f"Category review error: {e}")
        return {"suggestions": {}}


async def generate_cross_topic_insights(categories: list[dict], top_entities: list[dict]) -> dict:
    """Generate insights across different knowledge categories."""
    provider = get_provider()
    if not provider or not await provider.is_available():
        return {"insights": []}

    cat_names = ", ".join([c['name'] for c in categories[:10]])
    ent_names = ", ".join([e['name'] for e in top_entities[:15]])

    prompt = f"""请分析知识库的整体结构并发现跨领域洞察：

知识库分类: {cat_names}
高频实体: {ent_names}

以 JSON 返回：
{{
  "insights": [
    {{"topic": "洞察主题", "description": "发现", "related_categories": ["分类1"], "importance": 0.0-1.0}}
  ],
  "knowledge_gaps": ["缺失领域1", "缺失领域2"],
  "emerging_topics": ["新兴主题1"]
}}"""

    try:
        response = await provider.chat(
            messages=[{"role": "system", "content": ORGANIZER_SYSTEM}, {"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.3, json_mode=True,
        )
        return _parse_json_response(response.text) or {"insights": [], "knowledge_gaps": [], "emerging_topics": []}
    except Exception:
        return {"insights": [], "knowledge_gaps": [], "emerging_topics": []}


# ── Helpers ───────────────────────────────────────

def _parse_json_response(text: str) -> Optional[dict]:
    """Extract JSON from AI response text."""
    if not text:
        return None
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON block
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _fallback_organize(title: str, content: str) -> dict:
    """Local NLP fallback when no AI provider is available."""
    keywords = nlp_pipeline.extract_keywords(content, top_n=10)

    return {
        "classification": {
            "suggested_category": "未分类",
            "confidence": 0.3,
            "is_new_category": False,
            "alternative_categories": [],
        },
        "summary": {
            "one_liner": content[:100] + ("..." if len(content) > 100 else ""),
            "key_points": keywords[:5],
            "difficulty": "intermediate",
        },
        "entities": [{"name": kw, "type": "concept", "description": ""} for kw in keywords[:5]],
        "relationships": [],
        "quality": {"importance": 0.5, "completeness": 0.5, "is_core_knowledge": False},
        "suggestions": {"category_actions": [], "merge_suggestions": []},
    }
