import faiss
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_PATH = "data/faiss.index"
ID_MAP_PATH = "data/id_map.json"


class FaissStore:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dim = 384
        self.id_map = []
        self.id_set = set()

        os.makedirs("data", exist_ok=True)

        # 增量加载 FAISS 索引
        if os.path.exists(INDEX_PATH):
            self.index = faiss.read_index(INDEX_PATH)
        else:
            self.index = faiss.IndexFlatIP(self.dim)  # 余弦相似

        # 增量加载 ID 列表
        if os.path.exists(ID_MAP_PATH):
            with open(ID_MAP_PATH, "r", encoding="utf-8") as f:
                self.id_map = json.load(f)
                self.id_set = set(self.id_map)

    def add(self, news_id: int, text: str):
        # 去重
        if news_id in self.id_set:
            print(f"新闻 ID {news_id} 已存在，跳过添加")
            return

        # 向量化
        emb = self.model.encode([text], normalize_embeddings=True)
        self.index.add(np.array(emb, dtype="float32"))

        # 更新 ID 列表
        self.id_map.append(news_id)
        self.id_set.add(news_id)

    def search(self, query: str, top_k=5):
        q_emb = self.model.encode([query], normalize_embeddings=True)
        scores, idxs = self.index.search(np.array(q_emb, dtype="float32"), top_k)

        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < len(self.id_map):
                results.append({"news_id": self.id_map[idx], "score": float(score)})
        return results

    def save(self):
        # 保存 FAISS 索引
        faiss.write_index(self.index, INDEX_PATH)

        # 增量保存 ID 列表
        if os.path.exists(ID_MAP_PATH):
            with open(ID_MAP_PATH, "r", encoding="utf-8") as f:
                old_ids = json.load(f)
        else:
            old_ids = []

        # 合并去重（保留顺序）
        combined_ids = old_ids + [i for i in self.id_map if i not in old_ids]

        with open(ID_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(combined_ids, f, ensure_ascii=False, indent=2)
