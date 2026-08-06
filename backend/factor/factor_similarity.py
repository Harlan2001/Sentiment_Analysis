"""
因子相似度计算引擎
使用预训练模型计算因子语义相似度，防止创建语义重复的新因子。
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

import jieba
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config.config import MODEL_DIR
from backend.factor.factor_management import get_factors_from_db

logger = logging.getLogger(__name__)


# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@dataclass
class SimilarityResult:
    """相似度计算结果"""

    factor_code: str
    factor_name: str
    similarity_score: float
    cosine_similarity: float
    keyword_overlap: float
    category: str
    factor_type: str


class FactorSimilarityEngine:
    """
    因子相似度计算引擎
    使用text2vec-base-chinese模型计算语义相似度
    结合关键词重合度进行综合评分
    """

    def __init__(self):
        self.model = None
        self.standard_factors = []
        self.standard_embeddings = {}
        self._initialized = False
        self._init_lock = Lock()

    def initialize(self, model_name="all-MiniLM-L6-v2"):
        """初始化引擎，加载模型和标准因子"""
        if self._initialized:
            return

        # 加锁避免并发场景重复初始化
        with self._init_lock:
            if self._initialized:
                return

            try:
                model_path = Path(MODEL_DIR) / model_name
                if not model_path.exists():
                    raise FileNotFoundError(f"本地模型目录不存在: {model_path}")

                # 仅加载一次模型（删除冗余的_model_name判断）
                if self.model is None:
                    self.model = SentenceTransformer(
                        str(model_path), local_files_only=True
                    )
                logger.info("相似度模型加载成功")
            except ImportError:
                logger.warning("sentence-transformers未安装，使用备用方法")
                self.model = None

            # 加载标准因子
            self.standard_factors = get_factors_from_db()
            logger.info("加载 %d 个标准因子", len(self.standard_factors))

            # 预计算标准因子嵌入
            if self.model:
                self._precompute_embeddings()

            self._initialized = True
            logger.info("相似度引擎初始化完成")

    def _precompute_embeddings(self):
        """预计算所有标准因子的文本嵌入"""
        if not self.model:
            return

        factor_texts = []
        factor_codes = []

        for factor in self.standard_factors:
            text = f"{factor['name']} {factor['code']} {factor['category']}"
            factor_texts.append(text)
            factor_codes.append(factor["code"])

        # 批量计算嵌入（已归一化）
        embeddings = self.model.encode(factor_texts, normalize_embeddings=True)
        self.standard_embeddings = dict(zip(factor_codes, embeddings))
        logger.info("预计算 %d 个因子嵌入", len(self.standard_embeddings))

    def calculate_similarity(
        self, new_factor_text: str, top_k: int = 1
    ) -> List[SimilarityResult]:
        """
        计算新因子与标准因子的相似度
        Args:
            new_factor_text: 新因子文本描述
            top_k: 返回最相似的前k个结果
        Returns:
            相似度结果列表，按相似度降序排序
        """
        if not self._initialized:
            self.initialize()

        # 计算新因子嵌入
        new_embedding = self.model.encode([new_factor_text], normalize_embeddings=True)[
            0
        ]

        results = []
        for factor in self.standard_factors:
            factor_code = factor["code"]
            if factor_code not in self.standard_embeddings:
                continue

            factor_embedding = self.standard_embeddings[factor_code]

            # ✅ 优化：归一化向量直接点积 = 余弦相似度（删除冗余方法）
            cosine_sim = float(np.dot(new_embedding, factor_embedding))

            # 计算关键词重合度
            keyword_sim = self._calculate_keyword_overlap(new_factor_text, factor)

            # 综合评分：70%语义相似度 + 30%关键词重合度
            combined_score = 0.7 * cosine_sim + 0.3 * keyword_sim

            results.append(
                SimilarityResult(
                    factor_code=factor_code,
                    factor_name=factor["name"],
                    similarity_score=combined_score,
                    cosine_similarity=cosine_sim,
                    keyword_overlap=keyword_sim,
                    category=factor["category"],
                    factor_type=factor["factor_type"],
                )
            )

        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]

    def _calculate_keyword_overlap(
        self, new_text: str, standard_factor: Dict[str, Any]
    ) -> float:
        """计算关键词重合度"""
        try:
            new_words = set(jieba.cut(new_text.lower()))
            standard_words = set(jieba.cut(standard_factor["name"].lower()))
            code_words = set(jieba.cut(standard_factor["code"].lower()))
        except ImportError:
            new_words = set(new_text.lower().split())
            standard_words = set(standard_factor["name"].lower().split())
            code_words = set(standard_factor["code"].lower().split())

        # 计算Jaccard相似度
        intersection = len(new_words & standard_words) + len(new_words & code_words)
        union = len(new_words | standard_words | code_words)
        return intersection / union if union else 0.0

    def reload_factors(self):
        """重新加载因子库和嵌入，在新增因子后调用"""
        self.standard_factors = get_factors_from_db()
        if self.model:
            self._precompute_embeddings()
        logger.info("相似度引擎已重载，当前因子数: %d", len(self.standard_factors))


# 全局单例实例
_similarity_engine = None


def get_similarity_engine() -> FactorSimilarityEngine:
    """获取相似度引擎单例"""
    global _similarity_engine
    if _similarity_engine is None:
        _similarity_engine = FactorSimilarityEngine()
    return _similarity_engine
