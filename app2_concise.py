import sqlite3
from typing import Optional, Tuple
from textwrap import dedent

import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from opencc import OpenCC
from embeddings.semantic_search import semantic_search

cc_s2t = OpenCC("s2tw")   # 简→繁
cc_t2s = OpenCC("t2s")


DB_SOURCES = {
    "南普陀版": "lamrim_nanputuo.db",
    "鳳山寺版": "lamrim_fengshan.db",
}
CONTEXT_BEFORE = 1
CONTEXT_AFTER = 1
MIN_CHARS = 100


st.set_page_config(
    page_title="廣論智慧搜尋",
    page_icon="📖",
    layout="wide",
)

st.markdown('<div id="top"></div>', unsafe_allow_html=True)

#字体大小
if "font_scale" not in st.session_state:
    st.session_state.font_scale = 1


query_params = st.query_params
default_keyword = query_params.get("q", "")
default_source = query_params.get("source", "")
default_scope = query_params.get("scope", "")
default_kepan = query_params.get("kepan", "")

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
        margin: -24px 0 12 0 !important;
        font-size: 24px;
        font-weight: 800;
        color: #2D2A25;
    }

    /* 找到结果叫什么 */
    .result-keyword {
        margin-left: 1px;
        color: #8C4303;
        font-weight: 800;
        font-size: 24px !important;
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
        gap: 10px;
    }

    .lecture-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .header-links p {
        margin: 0 0 6px 0 !important;
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

    .version-badge {
        display: inline-block;
        padding: 9px 18px;
        border-radius: 7px;
        background: #693000;
        color: #fff;
        font-size: 18px;
        font-weight: 700;
    }

    .result-index,
    .lecture-title {
        color: #693000;
        font-size: {27 * scale}px;
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
        line-height: 1.9 !important;
        font-weight: 400 !important;
    }

    /* 广论原文 */
    .transcript-html-container span {
        color: #111 !important;
        font-family: "STKaiti", "KaiTi", serif !important;
        font-weight: 500 !important;
        line-height: 2 !important;
    }

    .transcript-html-container blockquote,
    .transcript-html-container blockquote p,
    .transcript-html-container blockquote * {
        color: #111 !important;
        font-family: "STKaiti", "KaiTi", serif !important;
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

    .focus-context-block {
        opacity: 1 !important;
    }

    /* 一键回顶 */
    .back-to-top {
        position: fixed;
        bottom: 25px;
        right: 25px;

        width: 56px;
        height: 56px;

        border-radius: 50%;
        background: #693000;

        color: white;
        text-align: center;
        line-height: 56px;

        font-size: 24px;

        cursor: pointer;
        z-index: 9999;
    }

    div[data-testid="stExpander"] {
        margin-bottom: 0px !important;
    }

    /* 字体整个按钮 */
    button[kind="tertiary"]{
        background:#eee9e2 !important;
        color:#5b4a3c !important;

        border:none !important;
        border-radius:999px !important;

        height:34px !important;
        min-width:34px !important;

        transition:all .15s ease;
    }

    /* hover */
    button[kind="tertiary"]:hover{
        background:#e3ddd5 !important;
    }

    /* 点击时 */
    button[kind="tertiary"]:active{
        background:white !important;
    }

    /* 字 */
    button[kind="tertiary"] p{
        color:#5b4a3c !important;
        font-weight:600 !important;
    }

    a {
        color: #8c4303 !important;
    }

    @media (max-width: 768px) {

        .main-title {
            font-size: 30px !important;
            margin-top: 20px !important;
        }

        .subtitle {
            font-size: 15px !important;
            margin-bottom: 24px !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.result-count) {
            margin-bottom: 8px !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.result-count) > div:nth-child(2) {
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        .result-count,
        .result-count p,
        .result-keyword {
            font-size: 24px !important;
            line-height: 1.35 !important;
            margin-bottom: -10px !important;
        }

        /* 手机端：字体不显示 */
        .font-control-title {
            display: none !important;
        }

        button[kind="primary"],
        button[kind="tertiary"] {
            display: none !important;
        }

        /* 卡片头部手机端改成上下排列 */
        .result-card-header {
            display: block !important;
            padding: 22px 20px !important;
        }

        .lecture-left {
            flex-wrap: wrap !important;
            gap: 10px !important;
        }

        .version-badge {
            padding: 8px 14px !important;
            font-size: 18px !important;
            writing-mode: horizontal-tb !important;
            white-space: nowrap !important;
        }

        .header-right {
            align-items: flex-start !important;
            margin-top: 18px !important;
        }

        .tag {
            font-size: 16px !important;
            max-width: 100% !important;
            white-space: normal !important;
        }

        .context-box {
            margin: 0 16px 24px 16px !important;
            padding: 22px 18px !important;
        }

        .transcript-html-container span,
        .transcript-html-container blockquote,
        .transcript-html-container blockquote p,
        .transcript-html-container blockquote * {
            font-family: "Songti TC", "Songti SC", "STSong", "Noto Serif TC", serif !important;
        }

        .back-to-top {
            width: 52px !important;
            height: 52px !important;
            right: 18px !important;
            bottom: 85px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 语言
if "lang" not in st.session_state:
    st.session_state.lang = "繁體"

lang_col1, lang_col2 = st.columns([18, 2])

with lang_col2:
    button_label = "🌐 繁體" if st.session_state.lang=="繁體" else "🌐 简体"
    if st.button(button_label):
        st.session_state.lang = (
            "簡體"
            if st.session_state.lang=="繁體"
            else "繁體"
        )
        st.rerun()
display_lang = st.session_state.lang

def t(text):
    text = str(text or "")
    return cc_t2s.convert(text) if display_lang == "簡體" else text

st.markdown("""
            <style>
            div[data-testid="stButton"] button {
                white-space: nowrap !important;
            }
            </style>
            """, unsafe_allow_html=True)

st.markdown(
    f'<div class="main-title">{t("廣論智慧搜尋")}</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="subtitle">{t("輸入關鍵詞，快速定位廣論手抄稿中的講次、科判與上下文")}</div>',
    unsafe_allow_html=True,
)

# 搜索栏
# 关键词
search_col, button_col = st.columns([8,2], vertical_alignment="bottom")

with search_col:
    keyword = st.text_input(
        t("請輸入關鍵詞："),
        value=default_keyword,
        placeholder=t("需完全匹配，例如：皈依三寶、念死無常"),
    )

    search_keyword = cc_s2t.convert(keyword)

display_keyword = t(search_keyword)

with button_col:
    search_clicked = st.button(t("檢索"), use_container_width=True)

# search_mode = st.radio(
#     t("搜尋模式："),
#     [t("精確搜尋"), t("智慧模糊搜尋")],
#     horizontal=True,
# )


st.markdown(
    f"""
    <div style="font-weight:700;
    margin-bottom:-8px;">
    {t("搜尋版本：")}
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, _ = st.columns([1.6, 1.6, 7.2])
selected_sources = []

with col1:
    if st.checkbox(
        t("南普陀版"),
        value=True,
        key="source_nanputuo",
    ):
        selected_sources.append("南普陀版")

with col2:
    if st.checkbox(
        t("鳳山寺版"),
        key="source_fengshan",
    ):
        selected_sources.append("鳳山寺版")


with st.expander(t("🔎 科判高級分類檢索")):

    st.markdown(
        f"""
        <div style="font-weight:700
        margin-bottom:-8px;">
        {t('三士道：')}
        </div>
        """,
        unsafe_allow_html=True,
    )

    scope_options = ["道前基礎", "下士道", "中士道", "上士道"]

    selected_scopes = []
    cols = st.columns(4)

    for i, item in enumerate(scope_options):
        with cols[i % 4]:
            if st.checkbox(t(item), key=f"scope_{item}"):
                selected_scopes.append(item)

    scope_filter = selected_scopes

    st.markdown(
        f"""
        <div style="font-weight:700
        margin-bottom:-8px;">
        {t('具體科判：')}
        </div>
        """,
        unsafe_allow_html=True,
    )
    subsection_options = [
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
        ]
    
    selected_subsections = []
    cols = st.columns(4)

    for i, item in enumerate(subsection_options):
        with cols[i % 4]:
            if st.checkbox(t(item), key=f"subsection_{item}"):
                selected_subsections.append(item)

    display_map = {t(x): x for x in subsection_options}
    subsection_filter = selected_subsections
    

def search_lectures(
    search_keyword: str,
    selected_sources=None,
    scope_filters=None,
    subsection_filters=None,
    ) -> list[sqlite3.Row]:

    selected_sources = selected_sources or ["南普陀版"]
    all_rows = []

    for source_name in selected_sources:
        DB_PATH = DB_SOURCES[source_name]

        query = """
            SELECT volume, title, toc_title, section, subsection, url, content_html, content_text
            FROM lectures
            WHERE content_text LIKE ?
        """

        params = [f"%{search_keyword}%"]

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
            rows = conn.execute(query, params).fetchall()
            
            for row in rows:
                row_dict = dict(row)
                row_dict["source"] = source_name
                all_rows.append(row_dict)

    return all_rows


def prepare_html(content_html: str, search_keyword: str) -> Tuple[str, Optional[str]]:
    soup = BeautifulSoup(content_html or "", "html.parser")

    # blocks = [
    #     p for p in soup.find_all("p")
    #     if p.get_text(strip=True)
    # ]

    blocks = []

    for element in soup.find_all(["p", "blockquote", "h4"]):
        if element.name == "p" and element.find_parent("blockquote"):
            continue

        if element.get_text(strip=True):
            blocks.append(element)

    match_idx = next(
        (
            i for i, block in enumerate(blocks)
            if search_keyword in block.get_text()
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

        if search_keyword in node:
            highlighted_html = str(node).replace(
                search_keyword,
                f"<strong>{search_keyword}</strong>",
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
        if i == match_idx:
            block["class"] = block.get("class", []) + ["focus-context-block"]
        else:
            block["class"] = block.get("class", []) + ["faded-context-block"]

    return "".join(str(block) for block in visible_blocks), keyword_time

def convert_html(html):
    if display_lang != "簡體":
        return html

    soup = BeautifulSoup(html, "html.parser")

    for node in soup.find_all(string=True):
        if node.parent.name in ["script", "style"]:
            continue
        node.replace_with(cc_t2s.convert(str(node)))

    return str(soup)

scale = st.session_state.font_scale
st.markdown(f"""
            <style>
            .result-card,
            .context-label,
            .header-links p {{
                font-size: {16 * scale}px !important;
            }}

            .result-index,
            .lecture-title {{
                font-size: {27 * scale}px !important;
            }}

            .version-badge {{
                font-size: {18 * scale}px !important;
            }}

            .tag {{
                font-size: {17 * scale}px !important;
            }}

            .transcript-html-container p {{
                font-size:{16*scale}px !important;
            }}

            .transcript-html-container span,
            .transcript-html-container blockquote,
            .transcript-html-container blockquote p,
            .transcript-html-container blockquote * {{
                font-size:{20*scale}px !important;
            }}
            </style>
            """, unsafe_allow_html=True)

if search_keyword:
    # if search_mode == t("智慧模糊搜尋"):
    #     rows = semantic_search(search_keyword,selected_sources=selected_sources,top_k=20,)
    # else:
    rows = search_lectures(search_keyword,selected_sources,scope_filter,subsection_filter,)

    st.query_params["q"] = search_keyword
    if selected_sources:
        st.query_params["source"] = ",".join(selected_sources)
    if scope_filter:
        st.query_params["scope"] = ",".join(scope_filter)
    if subsection_filter:
        st.query_params["kepan"] = ",".join(subsection_filter)
    

    result_left, result_right = st.columns([7.6, 2.4], vertical_alignment="center")

    with result_left:
        st.markdown(
            f"""
            <div class="result-count">
                {t("找到")} {len(rows)} {t("個講次包含")}：
                <span class="result-keyword">{display_keyword}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with result_right:
        st.markdown(
            """
            <style>
            div[data-testid="stHorizontalBlock"]:has(button[kind="tertiary"]) {
                margin-top: -20px !important;
                margin-bottom: -20px !important;
            }

            button[kind="primary"]{
                background:#8C4303 !important;
                color:white !important;
                border:none !important;
                border-radius:999px !important;

                height: 34px !important;
                min-width: 34px !important;
                width: 34px !important;
                padding: 0 !important;
            }

            button[kind="primary"] p{
                color:white !important;
                font-weight:700 !important;
            }

            .font-control-title {
                text-align: left;
                margin: -18px 0 30px 0;
                color: #5b4a3c;
                font-size: 14px;
                font-weight: 600;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        def btn_type(value):
            return "primary" if st.session_state.font_scale == value else "tertiary"

        st.markdown(
            f'<div class="font-control-title">{t("文字縮放")}：</div>',
            unsafe_allow_html=True,
        )
        c11, c12, c13, c14, c15 = st.columns(5, gap="small")

        with c11:
            if st.button("⊖", key="font_minus", type="tertiary"):
                st.session_state.font_scale = max(0.85, st.session_state.font_scale - 0.1)
                st.rerun()

        with c12:
            if st.button("小", key="font_small", type=btn_type(1.0)):
                st.session_state.font_scale = 1
                st.rerun()

        with c13:
            if st.button("中", key="font_medium", type=btn_type(1.25)):
                st.session_state.font_scale = 1.25
                st.rerun()

        with c14:
            if st.button("大", key="font_large", type=btn_type(1.5)):
                st.session_state.font_scale = 1.5
                st.rerun()

        with c15:
            if st.button("⊕", key="font_plus", type="tertiary"):
                st.session_state.font_scale = min(1.75, st.session_state.font_scale + 0.1)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


    for idx, row in enumerate(rows,start=1):
        html, keyword_time = prepare_html(row["content_html"], search_keyword)
        html = convert_html(html)

        with st.container():
            card_html = (
                f'<div class="result-card">'
                f'<div class="result-card-header">'
                f'<div class="header-left">'
                f'<div class="lecture-left">'
                f'<div class="result-index">#{idx}</div>'
                f'<span class="version-badge">{t(row["source"])}</span>'
                f'<span class="lecture-title">{t(row["toc_title"] or row["title"])}</span>'
                f'</div>'

                f'<div class="header-links">'
                # f'<p><strong>講次：</strong> 第 {row["volume"]} 講</p>'
                # f'<p><strong>標題：</strong> {row["toc_title"] or row["title"]}</p>'
                # f'<p><strong>科判：</strong> {row["section"] or ""}</p>'
                # f'<p><strong>廣論段落：</strong> {row["subsection"] or ""}</p>'
                f'<p><strong>原文：</strong> <a href="{row["url"]}">{t("打開網頁")}</a></p>'
                f'{f"<p><strong>時間：</strong> {keyword_time}</p>" if keyword_time else ""}'
                f'</div>'
                f'</div>'

                f'<div class="header-right">'
                f'<span class="tag tag-kepan">科判：{t(row["section"]) or ""}</span>'
                f'<span class="tag">{t("廣論段落")}：{t(row["subsection"]) or ""}</span>'
                f'</div>'
                f'</div>'

                f'<div class="context-label">{t("原文語境追溯")} CONTEXT WINDOW</div>'
                # f'<p><strong>{t("相似度")}：</strong> {row["score"]:.2f}</p>" if "score" in row else "'

                f'<div class="context-box">'
                f'<div class="transcript-html-container">{html}</div>'
                f'</div>'
                f'</div>'
            )

            st.markdown("""
                        <style>
                        .back-to-top {
                            position: fixed;
                            bottom: 90px;
                            right: 25px;

                            width: 60px;
                            height: 60px;

                            border-radius: 50%;
                            background: #693000;

                            color: white !important;
                            text-decoration: none !important;

                            display: flex;
                            align-items: center;
                            justify-content: center;

                            font-size: 28px;
                            font-weight: bold;

                            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                            z-index: 9999;
                        }
                        
                        .back-to-top:hover {
                            background: #8C4303;
                        }
                        </style>

                        <a href="#top" class="back-to-top">
                        ↑
                        </a>
                        
                        """, unsafe_allow_html=True)
            
            st.markdown(card_html, unsafe_allow_html=True)

# streamlit run app2_concise.py
# git add .
# git commit -m "这版update内容"
# git push origin main