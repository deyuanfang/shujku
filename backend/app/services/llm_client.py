"""Claude API client for document analysis — summarization, entity extraction, relationship detection."""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Anthropic client
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from anthropic import AsyncAnthropic
            _client = AsyncAnthropic(api_key=settings.llm_api_key)
        except ImportError:
            logger.warning("anthropic package not installed. LLM features disabled.")
            return None
    if not settings.llm_api_key:
        return None
    return _client


async def analyze_document(
    title: str,
    content: str,
    tasks: list[str] | None = None,
) -> dict:
    """Analyze a document using Claude API.

    Args:
        title: Document title.
        content: Document text content (will be truncated if too long).
        tasks: List of tasks to perform: 'summarize', 'extract_entities', 'extract_relationships', 'suggest_tags'.
               Defaults to all.

    Returns:
        Dict with results keyed by task name.
    """
    client = _get_client()
    if client is None:
        return {"error": "LLM not configured — set llm_api_key in settings"}

    if tasks is None:
        tasks = ["summarize", "extract_entities", "extract_relationships", "suggest_tags"]

    # Truncate content to fit context window (leave room for prompt + response)
    max_content_chars = 8000
    if len(content) > max_content_chars:
        content = content[:max_content_chars] + "\n\n[... 内容已截断 ...]"

    model = settings.llm_model

    results = {}

    # ── Summarization ──────────────────────────────
    if "summarize" in tasks:
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=500,
                system="你是一个专业的知识管理助手。请用中文输出。",
                messages=[{
                    "role": "user",
                    "content": f"""请为以下文档生成一个简洁的摘要（100-200字），并提取 3-5 个关键要点。

标题：{title}

内容：
{content}

请用 JSON 格式回复：
{{"summary": "摘要内容", "key_points": ["要点1", "要点2", "要点3"]}}"""
                }],
            )
            text = response.content[0].text if response.content else ""
            # Try to parse JSON from response
            try:
                # Handle possible markdown code block wrapping
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                summary_data = json.loads(text.strip())
                results["summary"] = summary_data.get("summary", "")
                results["key_points"] = summary_data.get("key_points", [])
            except (json.JSONDecodeError, IndexError):
                results["summary"] = text.strip()
                results["key_points"] = []
            results["summary_tokens"] = {
                "prompt": response.usage.input_tokens if response.usage else 0,
                "completion": response.usage.output_tokens if response.usage else 0,
            }
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            results["summary"] = None
            results["summary_error"] = str(e)

    # ── Entity Extraction ──────────────────────────
    if "extract_entities" in tasks:
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=1000,
                system="你是一个专业的信息提取助手。请用中文输出。",
                messages=[{
                    "role": "user",
                    "content": f"""请从以下文档中提取命名实体。实体类型包括：
- person (人物)
- organization (组织/公司)
- location (地点)
- concept (概念/术语)
- event (事件)
- technology (技术/工具/框架)
- other (其他)

对每个实体，提供名称、类型和简短描述。

标题：{title}

内容：
{content}

请用 JSON 数组格式回复，每个实体包含 name, type, description 字段：
[{{"name": "实体名", "type": "concept", "description": "简短描述"}}]

只提取有意义的实体，不要提取通用词。最多20个实体。"""
                }],
            )
            text = response.content[0].text if response.content else ""
            try:
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                entities = json.loads(text.strip())
                if isinstance(entities, list):
                    results["entities"] = entities
                else:
                    results["entities"] = []
            except (json.JSONDecodeError, IndexError):
                results["entities"] = []
            results["entity_tokens"] = {
                "prompt": response.usage.input_tokens if response.usage else 0,
                "completion": response.usage.output_tokens if response.usage else 0,
            }
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            results["entities"] = []

    # ── Relationship Extraction ────────────────────
    if "extract_relationships" in tasks and results.get("entities"):
        entities_for_prompt = json.dumps(
            [{"name": e["name"], "type": e["type"]} for e in results["entities"]],
            ensure_ascii=False,
        )
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=800,
                system="你是一个专业的知识图谱构建助手。请用中文输出。",
                messages=[{
                    "role": "user",
                    "content": f"""以下是从文档中提取的实体列表和文档内容。请找出实体之间的关系。

实体列表：
{entities_for_prompt}

文档内容：
{content}

请用 JSON 数组格式回复关系列表：
[{{"source": "实体A名称", "target": "实体B名称", "relation_type": "关系类型", "description": "关系描述"}}]

关系类型示例：uses, part_of, created_by, related_to, depends_on, implements, competes_with 等。最多10个关系。"""
                }],
            )
            text = response.content[0].text if response.content else ""
            try:
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                relationships = json.loads(text.strip())
                if isinstance(relationships, list):
                    results["relationships"] = relationships
                else:
                    results["relationships"] = []
            except (json.JSONDecodeError, IndexError):
                results["relationships"] = []
        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            results["relationships"] = []

    # ── Tag Suggestions ────────────────────────────
    if "suggest_tags" in tasks:
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=300,
                system="你是一个专业的内容分类助手。请用中文输出。",
                messages=[{
                    "role": "user",
                    "content": f"""请为以下文档建议 3-8 个标签。标签应该是简短的词组（2-6个字），用于分类和检索。

标题：{title}

内容：
{content}

请用 JSON 数组格式回复：["标签1", "标签2", "标签3"]"""
                }],
            )
            text = response.content[0].text if response.content else ""
            try:
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                tags = json.loads(text.strip())
                if isinstance(tags, list):
                    results["suggested_tags"] = tags
                else:
                    results["suggested_tags"] = []
            except (json.JSONDecodeError, IndexError):
                results["suggested_tags"] = []
        except Exception as e:
            logger.error(f"Tag suggestion failed: {e}")
            results["suggested_tags"] = []

    return results


async def generate_category_summary(
    category_name: str,
    documents: list[dict],
) -> dict:
    """Generate a summary for a category based on all its documents.

    Args:
        category_name: Name of the category.
        documents: List of {title, summary} dicts for documents in the category.
    """
    client = _get_client()
    if client is None:
        return {"error": "LLM not configured"}

    # Build a combined context from document summaries
    doc_contexts = []
    for i, doc in enumerate(documents[:10]):  # Max 10 docs to avoid token limits
        doc_contexts.append(f"{i+1}. {doc['title']}\n   {doc.get('summary', doc.get('raw_text', '')[:200])}")

    combined = "\n\n".join(doc_contexts)

    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=600,
            system="你是一个专业的知识管理助手。请用中文输出。",
            messages=[{
                "role": "user",
                "content": f"""以下是"{category_name}"分类下的多篇文档摘要。请总结这个分类的：
1. 核心主题（1-2句话）
2. 涵盖的主要子话题（3-5个要点）
3. 知识覆盖程度（是否有明显缺失的方面）

文档摘要：
{combined}

请用 JSON 格式回复：
{{"core_theme": "核心主题", "sub_topics": ["子话题1", "子话题2"], "coverage_gaps": "知识覆盖评估"}}"""
            }],
        )
        text = response.content[0].text if response.content else ""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return {"core_theme": text.strip(), "sub_topics": [], "coverage_gaps": ""}
    except Exception as e:
        logger.error(f"Category summary failed: {e}")
        return {"error": str(e)}
