import sqlite3
import streamlit as st

import re
from bs4 import BeautifulSoup

DB_PATH = "lamrim_nanputuo.db"

st.set_page_config(
    page_title="廣論智慧搜尋",
    page_icon="📖",
    layout="wide"
)

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
    font-family: "Noto Serif TC";
    margin-top: 30px;
}

.subtitle {
    text-align: center;
    color: #877367;
    font-size: 18px;
    margin-bottom: 35px;
}

.result-card {
    background: #fefefc;
    border: 1px solid #dac2b4;
    border-left: 6px solid #8C4303;
    border-radius: 18px;
    padding: 28px;
    margin: 24px 0;
    box-shadow: 0 4px 14px rgba(105,48,0,0.08);
}

.result-title {
    color: #693000;
    font-size: 24px;
    font-weight: 700;
}

.meta {
    color: #5c564f;
    font-size: 15px;
    line-height: 2.0;
}

.context {
    background: #F9F7F2;
    color: #2D2A25;
    border-left: 4px solid #8C4303;
    padding: 20px;
    border-radius: 12px;
    font-size: 17px;
    line-height: 2;
    margin-top: 16px;
    white-space: pre-wrap;
    font-family: 'Noto Sans TC';
}
            
.context-before,
.context-after {
    color: #877367;
    font-style: italic;
    line-height: 2;
    font-size: 18px;
}

.focus-range {
    background: #F9F7F2;
    border-left: 5px solid #8C4303;
    padding: 24px;
    margin: 20px 0;
    border-radius: 10px;
    line-height: 2.2;
    color: #2D2A25;
    font-size: 21px;
}

.focus-range strong {
    color: #8C4303;
    font-weight: 700;
}

.transcript-html {
    background: #FEFEFC;
    border-left: 5px solid #8C4303;
    padding: 28px 36px;
    border-radius: 14px;
    line-height: 2;
    color: #2D2A25;
    font-size: 18px;
}

.transcript-html p {
    margin-bottom: 1.4em;
}

.transcript-html strong,
.transcript-html b {
    font-weight: 800;
    color: #111;
    font-size: 1.08em;
}

.transcript-html mark {
    background: #E7A05A;
    color: #111;
    font-weight: 800;
    padding: 0 4px;
    border-radius: 3px;
}

.before-block,
.after-block {
    color: #877367;
    font-style: italic;
    font-size: 17px;
    line-height: 2;
    margin-bottom: 18px;
}

.focus-block {
    background: #F9F7F2;
    border-left: 5px solid #8C4303;
    padding: 22px 28px;
    margin: 22px 0;
    border-radius: 10px;
    color: #2D2A25;
    font-size: 20px;
    line-height: 2.1;
}

.focus-block strong,
.focus-block b {
    font-weight: 800;
    color: #111;
}

mark {
    background: #E7A05A;
    color: #111;
    font-weight: 800;
    padding: 0 4px;
    border-radius: 3px;
}


a {
    color: #8c4303 !important;
}
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="main-title">廣論智慧搜尋</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">輸入關鍵詞，快速定位南普陀版廣論手抄稿中的講次、科判與上下文</div>', unsafe_allow_html=True)

keyword = st.text_input("請輸入關鍵詞", placeholder="例如：深忍信、業果、菩提心、依止善知識")

def highlight_keyword(html, keyword):
    return html.replace(
        keyword,
        f"<mark>{keyword}</mark>"
    )

def get_context(text, keyword, before=180, after=420):
    idx = text.find(keyword)
    if idx == -1:
        return ""
    start = max(0, idx - before)
    end = min(len(text), idx + len(keyword) + after)
    return text[start:end]

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


if keyword:
    results = search(keyword)

    st.markdown(f"### 找到 {len(results)} 個講次包含：`{keyword}`")

    for row in results:
        paragraphs = row["content_text"].split("\n")
        matched_idx = None
        
        for i, p in enumerate(paragraphs):
            if keyword in p:
                matched_idx = i
                break

        if matched_idx is None:
            continue

        before = paragraphs[max(0, matched_idx - 2):matched_idx]
        focus = paragraphs[matched_idx]
        after = paragraphs[matched_idx + 1:matched_idx + 3]

        full_focus = paragraphs[matched_idx]

        idx = full_focus.find(keyword)
        start = max(0, idx - 80)
        end = min(len(full_focus), idx + len(keyword) + 180)

        focus = full_focus[start:end]

        if start > 0:
            focus = "..." + focus

        if end < len(full_focus):
            focus = focus + "..."

        focus = focus.replace(
            keyword,
            f"<strong>{keyword}</strong>"
        )
    
        with st.container(border=True):
            st.markdown(f"### 講次 {row['volume']}｜{row['toc_title'] or row['title']}")
            st.markdown(f"**科判：** {row['section'] or ''} ~ {row['subsection'] or ''}")
            st.markdown(f"**原文：** [打開原文網頁]({row['url']})")
            st.markdown("---")

            for p in before:
                if p.strip():
                    st.markdown(
                        f"<p class='context-before'>[前段] {p}</p>",
                        unsafe_allow_html=True
                    )

            st.markdown(
                f"<div class='focus-range'>{focus}</div>",
                unsafe_allow_html=True
            )

            for p in after:
                if p.strip():
                    st.markdown(
                        f"<p class='context-after'>[後段] {p}</p>",
                        unsafe_allow_html=True
                    )

# streamlit run app.py