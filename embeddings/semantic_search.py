import pickle
import streamlit as st
import faiss
from sentence_transformers import SentenceTransformer

# 加载模型
# 加载 FAISS 索引
# 加载 metadata
# 用户输入 → 转向量
# FAISS 找最相似段落
# 返回搜索结果


MODEL_NAME = "BAAI/bge-m3"
INDEX_PATH = "embeddings/lamrim.faiss"
METADATA_PATH = "embeddings/metadata.pkl"

@st.cache_resource
def load_semantic_assets():
    model = SentenceTransformer(MODEL_NAME)
    index = faiss.read_index(INDEX_PATH)

    with open(METADATA_PATH, "rb") as f:
        metadata = pickle.load(f)

    return model, index, metadata

_model = None
_index = None
_metadata = None


def load_semantic_assets():
    global _model, _index, _metadata

    if _model is None: #如果模型还没加载，就加载模型
        _model = SentenceTransformer(MODEL_NAME)

    if _index is None: #如果 FAISS 索引还没加载，就从文件读取
        _index = faiss.read_index(INDEX_PATH)

    if _metadata is None: #如果 metadata 还没加载，就读取 metadata.pkl。
        with open(METADATA_PATH, "rb") as f:
            _metadata = pickle.load(f)

    return _model, _index, _metadata

# query：用户输入，top_k：返回多少条
def semantic_search(query: str, selected_sources=None, top_k: int = 20):
    selected_sources = selected_sources or ["南普陀版"]

    model, index, metadata = load_semantic_assets()

    query_vector = model.encode(
        [query],
        normalize_embeddings=True,
    ).astype("float32")

    # 用 FAISS 搜索最相似的段落
    # score：相似度分数
    # ids：对应metadata的位置
    scores, ids = index.search(query_vector, top_k * 10)

    results = []

    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue

        if score < 0.45:
            continue
        
        item = dict(metadata[idx])

        if item["source"] not in selected_sources:
            continue

        item["score"] = float(score)
        item["content_html"] = f"<p>{item['paragraph']}</p>"

        results.append(item)

        if len(results) >= top_k:
            break

    return results