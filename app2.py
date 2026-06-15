import sqlite3
import streamlit as st
from bs4 import BeautifulSoup
import re

DB_PATH = "lamrim_nanputuo.db"

st.set_page_config(
    page_title="廣論智慧搜尋",
    page_icon="📖",
    layout="wide"
)

# 重新像素级校准的 CSS 样式表：完美还原官方段落、粗体标题以及时间戳
st.markdown("""
<style>
.stApp {
    background-color: #fbf9f4;
    color: #2D2A25;
    font-family: "Noto Serif TC", "Songti TC", serif;
}

.main-title {
    font-size: 42px;
    font-weight: 700;
    color: #693000;
    text-align: center;
    margin-top: 30px;
}

.subtitle {
    text-align: center;
    color: #877367;
    font-size: 18px;
    margin-bottom: 35px;
}

/* 官方手抄稿独立容器布局 */
.transcript-html-container {
    background: #fbf9f4 !important;
    padding: 10px 10px;
}

/* 【核心修复1】强制让所有原站段落组件独立成行，绝不揉成一团 */
.transcript-html-container p {
    font-size: 18px !important;
    line-height: 2.1 !important;
    margin-bottom: 24px !important;
    color: #2D2A25 !important;
    display: block !important;
    white-space: normal !important;
}

/* 【核心修复2】完美还原类似官方网页的左侧红棕色粗条科判、分二、一趣入等粗体行 */
.transcript-html-container h2, 
.transcript-html-container .book-title,
.transcript-html-container .chapter-title,
.transcript-html-container p:has(strong:only-child),
.transcript-html-container p strong {
    font-size: 22px;
    font-weight: 700;
    color: #111;
}

/* 如果某一行完全是标题（比如“分二：”），给它加上左侧红棕色粗边条 */
.transcript-html-container p:has(strong:only-child) {
    border-left: 4px solid #8C4303 !important;
    padding-left: 16px !important;
    margin-top: 28px !important;
    margin-bottom: 20px !important;
}

.transcript-html-container .section-title {
    border-left: 4px solid #8C4303 !important;
    padding-left: 16px !important;
    margin-top: 28px !important;
    margin-bottom: 20px !important;

    font-size: 30px !important;
    font-weight: 800 !important;
    color: #111 !important;
    line-height: 1.6 !important;
}

/* 【核心修复3】对网页中的原始时间戳数字进行样式包裹（还原灰色/棕色小徽章） */
.transcript-html-container span[class*="time"], 
.transcript-html-container span[style*="background-color"],
.transcript-html-container .audio-time {
    background-color: #b0a396 !important;
    color: #ffffff !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    font-size: 13px !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    margin-left: 6px !important;
    display: inline-block !important;
    font-weight: normal !important;
}

/* 上下文控制：隐藏不需要的远端段落，突出核心匹配段落 */
.hidden-context-block {
    display: none !important;
}

.faded-context-block {
    opacity: 0.65;
}

/* 关键词高亮 */
mark {
    background: #E7A05A !important;
    color: #111 !important;
    font-weight: 800;
    padding: 2px 4px;
    border-radius: 3px;
}

.transcript-html-container blockquote {
    border-left: 5px solid #8C4303;
    padding-left: 20px;
    margin: 30px 0;
    background: transparent;
}

.transcript-html-container blockquote p {
    font-size: 30px !important;
    font-weight: 800 !important;
    color: #111 !important;
    line-height: 1.6 !important;
    margin: 0 !important;
}
            
.transcript-html-container .seek-to,
.transcript-html-container .audio-time {
    background-color: #b0a396 !important;
    color: #ffffff !important;
    font-size: 18px !important;
    padding: 3px 8px !important;
    border-radius: 5px !important;
    margin-left: 8px !important;
    display: inline-block !important;
    font-weight: 700 !important;
}

a {
    color: #8c4303 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">廣論智慧搜尋</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">輸入關鍵詞，快速定位南普陀版廣論手抄稿中的講次、科判與上下文</div>', unsafe_allow_html=True)

keyword = st.text_input("請輸入關鍵詞", placeholder="例如：深忍信、業果、菩提心、依止善知識")

def search(keyword):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    rows = cur.execute("""
        SELECT volume, title, toc_title, section, subsection, url, content_text, content_html
        FROM lectures
        WHERE content_text LIKE ?
        ORDER BY volume
    """, (f"%{keyword}%",)).fetchall()
    
    conn.close()
    return rows

def generate_perfect_layout(content_html, keyword):
    soup = BeautifulSoup(content_html, "html.parser")

    # 把原网页 seek-to span 的 data-label 显示出来
    for sp in soup.select("span.seek-to"):
        label = sp.get("data-label")
        if label:
            sp.string = label
            sp["class"] = sp.get("class", []) + ["audio-time"]

    for text_node in soup.find_all(string=True):
        parent = text_node.parent
        if parent.name in ["script", "style", "mark", "span"]:
            continue

        text = str(text_node)

        if keyword in text:
            text = text.replace(keyword, f"<mark>{keyword}</mark>")

        if text != str(text_node):
            text_node.replace_with(BeautifulSoup(text, "html.parser"))

    # 2. 给“分二：”“一趣入...”这种短标题加 class
    blocks = soup.find_all(["p", "h1", "h2", "h3", "h4", "blockquote", "div"])

    valid_blocks = []
    for b in blocks:
        text = b.get_text(strip=True)
        if not text:
            continue

        valid_blocks.append(b)

    # 3. 找关键词所在段落，只显示上下文
    matched_idx = None
    for i, block in enumerate(valid_blocks):
        if keyword in block.get_text():
            matched_idx = i
            break

    if matched_idx is None:
        return str(soup)

    start_visible = max(0, matched_idx - 4)
    end_visible = min(len(valid_blocks), matched_idx + 5)

    for idx, block in enumerate(valid_blocks):
        if idx < start_visible or idx >= end_visible:
            block["class"] = block.get("class", []) + ["hidden-context-block"]
        elif idx != matched_idx:
            block["class"] = block.get("class", []) + ["faded-context-block"]

    return str(soup)

if keyword:
    results = search(keyword)
    st.markdown(f"### 找到 {len(results)} 個講次包含：`{keyword}`")
    
    for row in results:
        # 使用 Streamlit 官方大卡片包裹
        with st.container(border=True):
            st.markdown(f"### 講次 {row['volume']}｜{row['toc_title'] or row['title']}")
            st.markdown(f"**科判：** {row['section'] or ''} ~ {row['subsection'] or ''}")
            st.markdown(f"**原文：** [打開原文網頁]({row['url']})")
            st.markdown("---")
            
            # 【这里是关键改变】彻底抛弃老旧的字符串截取切片逻辑，直接把清洗标记后的原站 HTML 送入渲染
            html_layout = generate_perfect_layout(row["content_html"], keyword)
            
            st.markdown(
                f"<div class='transcript-html-container'>{html_layout}</div>",
                unsafe_allow_html=True
            )

# streamlit run app2.py