import sqlite3
from typing import Optional, Tuple
from textwrap import dedent

import streamlit as st
from bs4 import BeautifulSoup


DB_PATH = "lamrim_nanputuo.db"
CONTEXT_BEFORE = 1
CONTEXT_AFTER = 1
MIN_CHARS = 100


st.set_page_config(
    page_title="廣論智慧搜尋",
    page_icon="📖",
    layout="wide",
)


st.markdown(
    """
    <style>
    .stApp {
        background: #fbf9f4;
        color: #2D2A25;
        font-family: "Noto Serif TC", "Songti TC", serif;
    }

    .main-title {
        margin-top: 30px;
        text-align: center;
        font-size: 42px;
        font-weight: 700;
        color: #693000;
    }

    .subtitle {
        margin-bottom: 35px;
        text-align: center;
        font-size: 18px;
        color: #877367;
    }

    .stButton button {
        height: 48px;
        width: 100%;
        border-radius: 10px;
        background: #693000 !important;
        color: white !important;
        font-size: 18px;
        font-weight: 700;
    }

    /* 找到几个结果 */
    .result-count {
        margin: 35px 0 28px 0;
        font-size: 28px;
        font-weight: 800;
        color: #2D2A25;
    }

    /* 找到结果叫什么 */
    .result-keyword {
        margin-left: 3px;
        color: #8C4303;
        font-weight: 800;
    }

    /* 整张卡片 */
    .result-card {
        margin-bottom: 42px;
        border: 1px solid #d8c59f;
        border-radius: 14px;
        background: #fffdf8;
        overflow: hidden;
    }

    /* 卡片的title（第一个横线以上） */
    .result-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding: 28px 36px;
        border-bottom: 1px solid #e6dccb;
    }

    /* 84讲042B */
    .header-left {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 18px;
    }

    .lecture-left {
        display: flex;
        align-items: center;
        gap: 18px;
    }

    .header-links p {
        margin: 0 0 6px 0 !important;
        font-size: 16px;
        line-height: 1.5;
        color: #2D2A25;
    }

    .header-links strong {
        color: #693000;
        font-weight: 900;
    }

    .header-right {
        display: flex;
        flex-direction: column;
        gap: 10px;
        align-items: flex-end;
    }

    /* 84讲的深色底 */
    .lecture-badge {
        display: inline-block;
        margin-right: 16px;
        padding: 9px 18px;
        border-radius: 7px;
        background: #693000;
        color: #fff;
        font-size: 18px;
        font-weight: 700;
    }

    .lecture-title {
        color: #693000;
        font-size: 27px;
        font-weight: 700;
    }

    /* 科判；广论段落 */
    .lecture-tags {
        display: flex;
        gap: 12px;
        margin-left: auto;
    }

    .tag {
        display: inline-block;
        padding: 8px 15px;
        border-radius: 7px;
        background: #eee9e2;
        color: #5b4a3c;
        font-size: 17px;
        font-weight: 700;
    }

    .tag-kepan {
        background: #e8ddaa;
    }

    /* 原文语境……context window…… */
    .context-label {
        margin: 30px 36px 18px 36px;
        padding-left: 12px;
        border-left: 7px solid #b8ad83;
        color: #b8ad83;
        font-size: 16px;
        font-weight: 800;
        letter-spacing: 1px;
    }

    /* 正文区域大框 */
    .context-box {
        margin: 0 36px 32px 36px;
        padding: 30px 34px;
        border: 1px solid #e8ddca;
        border-radius: 12px;
        background: #fffaf0;
    }

    /* 普通段落 */
    .transcript-html-container {
        background: transparent !important;
        padding: 0 !important;
    }


    .transcript-html-container p {
        margin: 0 0 24px 0 !important;
        color: #080705 !important;
        font-size: 16px !important;
        line-height: 1.9 !important;
        font-weight: 400 !important;
    }

    /* 广论原文 */
    .transcript-html-container span {
        color: #111 !important;
        font-family: "STKaiti", "KaiTi", serif !important;
        font-size: 20px !important;
        font-weight: 500 !important;
        line-height: 2 !important;
    }


    /* 关键词 */
    .transcript-html-container strong,
    .transcript-html-container blockquote strong {
        color: #8C4303 !important;
        font-weight: 700 !important;
        background: linear-gradient(
        transparent 55%,
        #eadf9f 55%
        ) !important;
        padding: 0 2px !important;
    }

    /* 前文后文浅色 */
    .faded-context-block {
        opacity: 0.6;
    }

    a {
        color: #8c4303 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="main-title">廣論智慧搜尋</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">輸入關鍵詞，快速定位南普陀版廣論手抄稿中的講次、科判與上下文</div>',
    unsafe_allow_html=True,
)


# 搜索栏
search_col, button_col = st.columns([8,2], vertical_alignment="bottom")

with search_col:
    keyword = st.text_input(
        "請輸入關鍵詞：",
        placeholder="請使用繁體字，需完全匹配，例如：皈依三寶、念死無常",
    )

with button_col:
    search_clicked = st.button("檢索", use_container_width=True)

with st.expander("🔎 科判高級分類檢索"):

    scope_filter = st.multiselect(
        "三士道大階段：",
        ["顯示全部", "道前基礎", "下士道", "中士道", "上士道"],
        default=[],
        placeholder="顯示全部",
    )

    subsection_filter = st.multiselect(
        "具體科判：",
        [
            "全部步驟",
            "皈敬頌",
            "造者殊勝",
            "教授殊勝",
            "聽聞軌理",
            "親近善士",
            "修習軌理",
            "暇滿",
            "念死無常",
            "皈依三寶",
            "深信業果",
            "希求解脫",
            "思惟苦諦",
            "思惟集諦",
            "十二緣起",
            "大乘菩提心",
            "六波羅蜜多"
        ],
        default=[],
        placeholder="顯示全部",
    )
    

def search_lectures(
    keyword: str,
    scope_filters=None,
    subsection_filters=None,
    ) -> list[sqlite3.Row]:

    query = """
        SELECT volume, title, toc_title, section, subsection, url, content_html, content_text
        FROM lectures
        WHERE content_text LIKE ?
    """

    params = [f"%{keyword}%"]

    if scope_filters:
        placeholders = " OR ".join(["section LIKE ?"] * len(scope_filters))
        query += f" AND ({placeholders})"
        params.extend([f"%{item}%" for item in scope_filters])

    if subsection_filters:
        placeholders = " OR ".join(["subsection LIKE ?"] * len(subsection_filters))
        query += f" AND ({placeholders})"
        params.extend([f"%{item}%" for item in subsection_filters])

    query += " ORDER BY volume"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(query, params).fetchall()


def prepare_html(content_html: str, keyword: str) -> Tuple[str, Optional[str]]:
    soup = BeautifulSoup(content_html or "", "html.parser")

    blocks = [
        p for p in soup.find_all("p")
        if p.get_text(strip=True)
    ]

    match_idx = next(
        (
            i for i, block in enumerate(blocks)
            if keyword in block.get_text()
        ),
        None,
    )

    if match_idx is None:
        return str(soup), None
    
    keyword_block = blocks[match_idx]

    previous_time = keyword_block.find_previous("span", class_="seek-to")
    keyword_time = previous_time.get("data-label") if previous_time else None

    for span in soup.select("span.seek-to"):
        span.decompose()
    
    for node in soup.find_all(string=True):
        parent = node.parent

        if parent.name in {"script", "style", "mark"}:
            continue

        if keyword in node:
            highlighted_html = str(node).replace(
                keyword,
                f"<strong>{keyword}</strong>",
            )

            node.replace_with(
                BeautifulSoup(highlighted_html, "html.parser")
            )

    start = max(0, match_idx - CONTEXT_BEFORE)
    end = min(len(blocks), match_idx + CONTEXT_AFTER + 1)

    def visible_len() -> int:
        return sum(
            len(block.get_text(strip=True))
            for block in blocks[start:end]
        )

    while visible_len() < MIN_CHARS and (start > 0 or end < len(blocks)):
        if start > 0:
            start -= 1

        if end < len(blocks):
            end += 1

    visible_blocks = blocks[start:end]

    for i, block in enumerate(visible_blocks, start=start):
        if i != match_idx:
            block["class"] = block.get("class", []) + ["faded-context-block"]

    return "".join(str(block) for block in visible_blocks), keyword_time


if keyword:
    rows = search_lectures(keyword, scope_filter, subsection_filter)

    st.markdown(
        f"""
        <div class="result-count">
            找到 {len(rows)} 個講次包含：
            <span class="result-keyword">{keyword}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for row in rows:
        html, keyword_time = prepare_html(row["content_html"], keyword)

        with st.container():
            card_html = (
                f'<div class="result-card">'
                f'<div class="result-card-header">'
                f'<div class="header-left">'
                f'<div class="lecture-left">'
                f'<span class="lecture-badge">第 {row["volume"]} 講</span>'
                f'<span class="lecture-title">{row["toc_title"] or row["title"]}</span>'
                f'</div>'

                f'<div class="header-links">'
                # f'<p><strong>講次：</strong> 第 {row["volume"]} 講</p>'
                # f'<p><strong>標題：</strong> {row["toc_title"] or row["title"]}</p>'
                # f'<p><strong>科判：</strong> {row["section"] or ""}</p>'
                # f'<p><strong>廣論段落：</strong> {row["subsection"] or ""}</p>'
                f'<p><strong>原文：</strong> <a href="{row["url"]}">打開原文網頁</a></p>'
                f'{f"<p><strong>時間：</strong> {keyword_time}</p>" if keyword_time else ""}'
                f'</div>'
                f'</div>'

                f'<div class="header-right">'
                f'<span class="tag tag-kepan">科判：{row["section"] or ""}</span>'
                f'<span class="tag">廣論段落：{row["subsection"] or ""}</span>'
                f'</div>'
                f'</div>'

                f'<div class="context-label">原文語境前後雙向追溯 CONTEXT WINDOW</div>'

                f'<div class="context-box">'
                f'<div class="transcript-html-container">{html}</div>'
                f'</div>'
                f'</div>'
            )

            st.markdown(card_html, unsafe_allow_html=True)

# streamlit run app2_concise.py