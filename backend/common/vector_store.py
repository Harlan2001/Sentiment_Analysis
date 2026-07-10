import faiss
import json
import logging
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from backend.config.config import INDEX_PATH, ID_MAP_PATH, MODEL_DIR
from backend.common.database import execute_query, execute_update, execute_batch

logger = logging.getLogger(__name__)

# 全局单例实例
_faiss_store_instance = None
VECTOR_VERSION = "v1.0"  # 向量模型版本，升级模型时修改


def get_faiss_store() -> "FaissStore":
    """获取 FaissStore 单例实例（避免重复加载模型）"""
    global _faiss_store_instance
    if _faiss_store_instance is None:
        _faiss_store_instance = FaissStore()
    return _faiss_store_instance


class FaissStore:
    def __init__(self, model_name="all-MiniLM-L6-v2", auto_load=True):
        self.model = SentenceTransformer(
            f"{MODEL_DIR}/{model_name}", local_files_only=True
        )
        dim = self.model.get_embedding_dimension()
        if dim is None:
            raise RuntimeError("Failed to get embedding dimension from model")
        self.dim = dim

        self.index = None
        self.id_map = []
        self.id_set = set()
        self.loaded = False

        if auto_load:
            self.load()

    def load(self):
        if self.loaded:
            return

        self.loaded = True  # 只设一次

        if os.path.exists(INDEX_PATH) and os.path.exists(ID_MAP_PATH):
            logger.info("Loading FAISS index from disk...")
            self.index = faiss.read_index(str(INDEX_PATH))
            with open(ID_MAP_PATH, "r", encoding="utf-8") as f:
                self.id_map = json.load(f)
            self.id_set = set(self.id_map)


    def add(self, news_id: int, text: str) -> bool:
        self.load()
        assert self.index is not None

        if news_id in self.id_set:
            return False

        emb = self.model.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")

        # 1. 添加到 Faiss 索引
        self.index.add(emb)
        self.id_map.append(news_id)
        self.id_set.add(news_id)

        # 2. 持久化到 MySQL
        vector_blob = emb[0].tobytes()
        execute_update("""
            INSERT INTO news_vectors (news_id, vector, vector_version)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE vector = VALUES(vector)
        """, (news_id, vector_blob, VECTOR_VERSION))

        return True

    def batch_add(self, news_items: list[tuple[int, str]]) -> int:
        """批量添加新闻向量，提高导入效率"""
        self.load()
        assert self.index is not None

        # 过滤已存在的新闻
        new_items = [(news_id, text) for news_id, text in news_items if news_id not in self.id_set]
        if not new_items:
            return 0

        # 批量生成向量
        texts = [text for _, text in new_items]
        embs = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")

        # 1. 添加到 Faiss 索引
        self.index.add(embs)
        for news_id, _ in new_items:
            self.id_map.append(news_id)
            self.id_set.add(news_id)

        # 2. 批量插入 MySQL
        params = [
            (news_id, emb.tobytes(), VECTOR_VERSION)
            for (news_id, _), emb in zip(new_items, embs)
        ]
        execute_batch("""
            INSERT INTO news_vectors (news_id, vector, vector_version)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE vector = VALUES(vector)
        """, params)

        return len(new_items)

    def _search_vector(self, vector, top_k=5):
        self.load()
        if not self.index or self.index.ntotal == 0:
            return []

        scores, idxs = self.index.search(vector, top_k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append({"news_id": self.id_map[idx], "score": float(score)})
        return results

    def search(self, query: str, top_k: int = 5):
        q_emb = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        return self._search_vector(q_emb, top_k)

    def search_by_vector(self, vector, top_k=5):
        if isinstance(vector, list):
            vector = np.array(vector, dtype="float32")
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)
        return self._search_vector(vector.astype("float32"), top_k)

    def save(self):
        """保存索引到本地文件"""
        if self.index is None:
            return

        # 保存前确保目录存在
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        
        faiss.write_index(self.index, str(INDEX_PATH))

        with open(ID_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(self.id_map, f, ensure_ascii=False)
            
        # 保存后验证文件是否存在
        if not os.path.exists(INDEX_PATH) or not os.path.exists(ID_MAP_PATH):
            raise RuntimeError("索引文件保存失败，请检查目录权限")

    def size(self):
        self.load()
        assert self.index is not None
        return self.index.ntotal
    

    def get_pending_news(self, batch_size: int = 100) -> list[tuple[int, str]]:
        """获取待向量化的新闻列表（indexed = 0）

        Args:
            batch_size: 每批处理的最大数量

        Returns:
            [(news_id, full_text), ...] full_text = title + content
        """
        self.load()
        results = execute_query("""
            SELECT id, title, content
            FROM news
            WHERE indexed = 0
            AND content IS NOT NULL AND content != ''
            ORDER BY id ASC
            LIMIT %s
        """, (batch_size,))

        pending_items = []
        for news_id, title, content in results:
            full_text = f"{title} {content}"
            pending_items.append((news_id, full_text))

        return pending_items

    def mark_as_indexed(self, news_ids: list[int]) -> None:
        """批量标记新闻为已向量化（indexed = 1）

        Args:
            news_ids: 新闻ID列表
        """
        if not news_ids:
            return

        placeholders = ','.join(['%s'] * len(news_ids))
        execute_update(f"""
            UPDATE news SET indexed = 1 WHERE id IN ({placeholders})
        """, tuple(news_ids))
