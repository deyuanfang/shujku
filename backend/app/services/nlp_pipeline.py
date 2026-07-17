"""Chinese NLP pipeline: segmentation, TF-IDF classification, keyword extraction."""

import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Chinese stopwords — common words that don't carry meaning
_STOP_WORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你
会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 而 为 所以 因为
但是 可以 这个 那个 已经 如果 虽然 而且 或者 不过 还是 只是
之 与 及 其 啊 吧 呢 吗 哦 嗯 哈 呀 哇 呵
""".split())

# Category label examples for reference classification
_CATEGORY_KEYWORDS = {
    "技术笔记": ["编程", "代码", "算法", "框架", "前端", "后端", "数据库", "API", "Python", "JavaScript", "React", "AI", "机器学习"],
    "读书笔记": ["书", "作者", "章", "阅读", "读书", "笔记", "思想", "哲学", "文学", "历史"],
    "日常记录": ["今天", "下午", "明天", "周末", "会议", "工作", "生活", "计划"],
    "学习资料": ["学习", "教程", "课程", "知识点", "基础", "进阶", "入门", "指南", "文档"],
    "项目记录": ["项目", "需求", "设计", "开发", "测试", "部署", "上线", "迭代", "版本"],
}


class NLPPipeline:
    """Handles Chinese text segmentation, classification, and keyword extraction."""

    def __init__(self):
        self.vectorizer: TfidfVectorizer | None = None
        self.category_centroids: dict[str, np.ndarray] = {}
        self._jieba_loaded = False
        self._stop_words = _STOP_WORDS

    def _load_jieba(self):
        if not self._jieba_loaded:
            try:
                import jieba
                jieba.setLogLevel(20)  # Suppress jieba logs
                self._jieba_loaded = True
            except ImportError:
                pass

    def segment(self, text: str) -> list[str]:
        """Segment Chinese text into words using jieba."""
        self._load_jieba()
        import jieba

        # Remove punctuation and numbers
        text = re.sub(r"[^一-鿿\w]", " ", text)
        words = jieba.cut(text)
        return [w.strip() for w in words if w.strip() and w not in self._stop_words and len(w.strip()) > 1]

    def extract_keywords(self, text: str, top_n: int = 10) -> list[str]:
        """Extract top keywords using TF-IDF."""
        words = self.segment(text)
        if not words:
            return []

        # Use word frequency weighted by document length for importance
        from collections import Counter
        word_counts = Counter(words)
        total = sum(word_counts.values())
        if total == 0:
            return []

        # Simple TF scoring
        scored = [(word, count / total) for word, count in word_counts.items()]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [word for word, _ in scored[:top_n]]

    def classify(
        self,
        text: str,
        existing_categories: list[dict] | None = None,
    ) -> dict:
        """Classify text into the best matching category.

        Args:
            text: The document text to classify.
            existing_categories: List of {id, name} dicts from the database.

        Returns:
            dict with: category_id, category_name, confidence, keywords
        """
        keywords = self.extract_keywords(text, top_n=15)
        keyword_str = " ".join(keywords)

        if not existing_categories:
            # Fall back to keyword matching when no categories exist
            best_category = self._keyword_match(keywords)
            return {
                "category_id": None,
                "category_name": best_category,
                "confidence": 0.5,
                "keywords": keywords,
            }

        # TF-IDF based classification
        all_texts = [keyword_str]
        for cat in existing_categories:
            cat_keywords = _CATEGORY_KEYWORDS.get(cat["name"], [])
            if cat_keywords:
                all_texts.append(" ".join(cat_keywords))
            else:
                all_texts.append(cat["name"])

        vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
        try:
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            doc_vec = tfidf_matrix[0:1]
            cat_vecs = tfidf_matrix[1:]

            similarities = cosine_similarity(doc_vec, cat_vecs)[0]
            best_idx = int(np.argmax(similarities))
            confidence = float(similarities[best_idx])

            if confidence < 0.1:
                return {
                    "category_id": None,
                    "category_name": "未分类",
                    "confidence": confidence,
                    "keywords": keywords,
                }

            return {
                "category_id": existing_categories[best_idx]["id"],
                "category_name": existing_categories[best_idx]["name"],
                "confidence": confidence,
                "keywords": keywords,
            }
        except ValueError:
            return {
                "category_id": None,
                "category_name": "未分类",
                "confidence": 0.0,
                "keywords": keywords,
            }

    def _keyword_match(self, keywords: list[str]) -> str:
        """Fallback: match keywords against predefined category patterns."""
        scores = {}
        for cat, cat_words in _CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in cat_words or any(
                cw in kw for cw in cat_words
            ))
            if score > 0:
                scores[cat] = score

        if scores:
            return max(scores, key=scores.get)
        return "未分类"


# Singleton
nlp_pipeline = NLPPipeline()
