# 南普陀版《菩提道次第廣論》手抄稿爬虫

从 [大慈恩譯經基金會](https://www.amrtf.org/zh-hant/lamrim-transcripts-nanputuo/) 抓取全部讲次，并存入 SQLite。

## 安装

```bash
cd ~/Projects/lamrim-nanputuo-scraper
python3 -m pip install -r requirements.txt
```

## 运行

抓取全部 321 讲：

```bash
python3 scraper.py
```

测试（只抓前 3 讲）：

```bash
python3 scraper.py --limit 3
```

自定义数据库路径与请求间隔：

```bash
python3 scraper.py --db ./data/lamrim.db --delay 1.0
```

## 数据库结构

表 `lectures` 字段：

| 字段 | 说明 |
|------|------|
| `volume` | 讲次编号（000-320） |
| `slug` | URL slug |
| `wp_post_id` | WordPress 文章 ID |
| `title` | 页面标题 |
| `toc_title` | 目录中的短标题（如 001A） |
| `section` | 大章节（如 道前基礎） |
| `subsection` | 小章节（如 皈敬頌） |
| `duration` | 音频时长 |
| `url` | 原文链接 |
| `content_html` | 正文 HTML |
| `content_text` | 纯文本正文 |
| `published_at` | 发布时间 |
| `scraped_at` | 抓取时间 |

## 查询示例

```bash
sqlite3 lamrim_nanputuo.db "SELECT volume, title, section FROM lectures ORDER BY volume LIMIT 10;"
sqlite3 lamrim_nanputuo.db "SELECT COUNT(*) FROM lectures;"
```
