# AI News DJ

AI関連ニュースを自動収集し、日本語要約・タイトル翻訳・ジャンル分類を行うWebアプリです。
FastAPI + SQLite をバックエンドに、シングルページのダークテーマUIで動作します。

---

## 主な機能

- **RSSフィード取得** — TechCrunch AI・VentureBeat・OpenAI Blog・Anthropic News など10ソースから記事を一括取得
- **URL手動追加** — 任意のURLを入力して記事を取り込み
- **日本語タイトル翻訳** — 英語タイトルを自動で日本語に翻訳（一括翻訳対応）
- **日本語要約** — 【概要】と【ポイント】形式で箇条書きサマリーを生成（SSEストリーミング対応）
- **デイリーダイジェスト** — 当日の記事タイトルをもとに、ラジオ風の日本語ナレーションを生成
- **ジャンル分類** — キーワードスコアリングで5ジャンルに自動分類（モデル・研究 / ツール / ビジネス / 社会 / 開発アイデア）
- **全文検索** — SQLite FTS5による高速日本語検索
- **フィルタ** — ソース・ジャンル・日付・既読/未読・お気に入りで絞り込み
- **RSSソース管理** — UI上でRSSソースの追加・削除・有効/無効の切り替えが可能

---

## 技術スタック

| 層 | 使用技術 |
|---|---|
| バックエンド | Python 3.11 / FastAPI 0.115 / Uvicorn |
| データベース | SQLite 3（FTS5、WAL モード） |
| RSSパース | feedparser |
| Webスクレイピング | httpx + BeautifulSoup4 |
| AI要約・翻訳 | Claude API（claude-haiku-4-5）または Ollama（qwen3.5）|
| フロントエンド | Vanilla JS SPA（ダークテーマ） |

---

## 要約エンジン

環境変数 `SUMMARIZER` または `ANTHROPIC_API_KEY` の有無で自動切り替えます。

| 設定 | 動作 |
|---|---|
| `SUMMARIZER=claude` | Claude API（`claude-haiku-4-5-20251001`）を使用 |
| `SUMMARIZER=ollama` | ローカルのOllamaサーバー（`qwen3.5`）を使用 |
| 未設定 | `ANTHROPIC_API_KEY` があればClaude、なければOllama |

Claude APIでエラー（クレジット不足など）が発生した場合は、自動的にOllamaへフォールバックします。

---

## セットアップ

### 前提条件

- Python 3.11+
- （Claude使用時）Anthropic APIキー
- （Ollama使用時）[Ollama](https://ollama.com/) + `qwen3.5` モデル

### インストール

```bash
git clone https://github.com/YukiSuzuk1/AI-News-DJ.git
cd AI-News-DJ
pip install -r requirements.txt
```

### 環境変数

```bash
# Claude APIを使う場合
export ANTHROPIC_API_KEY=sk-ant-...

# Ollamaを明示的に使う場合
export SUMMARIZER=ollama
```

### サーバー起動

```bash
uvicorn main:app --reload --port 8000
```

ブラウザで `http://localhost:8000` を開いてください。

> **Windows (Anaconda) の場合**
> ```powershell
> C:\Users\<username>\anaconda3\python.exe -m uvicorn main:app --reload --port 8000
> ```

---

## API エンドポイント一覧

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/articles` | 記事一覧取得（検索・フィルタ対応） |
| GET | `/api/articles/{id}` | 記事詳細取得 |
| DELETE | `/api/articles/{id}` | 記事削除 |
| POST | `/api/articles/{id}/summarize` | 記事を日本語要約 |
| POST | `/api/articles/{id}/summarize/stream` | 要約をSSEストリーミング |
| POST | `/api/articles/{id}/translate-title` | タイトルを日本語翻訳 |
| POST | `/api/articles/{id}/read` | 既読にする |
| POST | `/api/articles/{id}/favorite` | お気に入りトグル |
| POST | `/api/fetch-rss` | RSSフィード一括取得 |
| POST | `/api/fetch-rss/stream` | RSS取得をSSEで進捗通知 |
| POST | `/api/add-url` | URLから記事を手動追加 |
| POST | `/api/translate-titles/stream` | 全タイトルを一括翻訳（SSE） |
| POST | `/api/classify-all` | 全記事をジャンル分類 |
| POST | `/api/digest/stream` | デイリーダイジェスト生成（SSE） |
| GET | `/api/sources` | RSSソース一覧 |
| POST | `/api/sources` | RSSソース追加 |
| DELETE | `/api/sources/{id}` | RSSソース削除 |
| PATCH | `/api/sources/{id}/toggle` | ソードの有効/無効切り替え |
| GET | `/api/count` | 記事件数取得 |
| GET | `/api/engine` | 使用中の要約エンジン確認 |

---

## ディレクトリ構成

```
.
├── main.py           # FastAPI ルーティング
├── database.py       # SQLite + FTS5（asyncio.to_thread パターン）
├── news_fetcher.py   # RSSフェッチ + URLスクレイピング
├── summarizer.py     # 要約・翻訳・ダイジェスト生成
├── classifier.py     # キーワードベースジャンル分類器
├── requirements.txt
├── start.bat         # Windows 起動スクリプト
└── static/
    └── index.html    # ダークテーマ SPA
```

---

## ライセンス

MIT
