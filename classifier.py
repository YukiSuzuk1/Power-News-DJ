"""
キーワードルールベースのジャンル分類器
各ジャンルのキーワードリストに対してスコアリングし、最も一致するジャンルを返す。
"""

from typing import Optional

# ── ジャンル定義 ────────────────────────────────────────────────────────────

GENRES: dict = {
    "research": {
        "label": "モデル・研究",
        "emoji": "🔬",
        "border": "#6e8efb",
        "keywords": [
            # モデル名
            "gpt-", "gpt4", "gpt 4", "gpt3", "gpt 3",
            "o1 ", "o3 ", "o4 ", "o1-", "o3-",
            "claude", "gemini", "llama", "mistral", "phi-", "phi ",
            "qwen", "deepseek", "grok", "command r", "mixtral",
            "falcon", "yi-", "solar ", "aya ", "jamba", "dbrx",
            "stable diffusion", "midjourney", "dall-e", "sora ", "flux ",
            "whisper", "wav2vec", "firefly", "imagen", "parti",
            "moonshot", "kimi ", "step-", "hunyuan", "ernie",
            "copilot ", "codegemma", "codellama", "starcoder",
            # パラメータサイズ
            "0.5b", "1b ", "1.5b", "3b ", "7b ", "8b ", "13b",
            "14b", "32b", "34b", "70b", "72b", "90b", "123b", "405b",
            # 研究・学習用語
            "benchmark", "arxiv", "preprint", "paper ", "research ",
            "dataset", "training run", "fine-tun", "finetuning",
            "pre-training", "pretraining", "post-training",
            "rlhf", "dpo ", "grpo", "ppo ", "sft ", "rft ",
            "alignment ", "reasoning ", "inference time",
            "chain of thought", "cot ", "tree of thought",
            "multimodal", "vision model", "language model",
            "large language", "foundation model", "base model",
            "parameter", "context window", "context length",
            "attention ", "transformer", "diffusion model",
            "accuracy ", "evaluation ", " eval ", "leaderboard",
            "agi ", "superintelligence", "capability",
            "weights", "checkpoint", "quantiz", "gguf", "ggml",
            "4-bit", "8-bit", "awq ", "gptq ",
            # モデルリリース
            "model release", "new model", "open model",
            "haiku", "sonnet", "opus", "turbo", "ultra", "flash",
            "thinking mode", "extended thinking",
            "prompt caching", "computer use",
            "function call", "tool use",
            # 研究テーマ
            "long context", "retrieval ", "memory ", "agent ",
            "hallucin", "grounding", "factual",
            "image generation", "text generation",
            "speech recognition", "translation model",
            "embedding model", "reranker",
        ]
    },
    "tools": {
        "label": "ツール・開発",
        "emoji": "🛠️",
        "border": "#3ab8c0",
        "keywords": [
            # ツール・ライブラリ
            "open source", "opensource", "github ", "repository", "repo ",
            "framework", "library", " sdk", " api ", "plugin", "extension",
            "mcp ", "model context protocol",
            "cursor ", "windsurf", "codeium", "tabnine", "continue ",
            "vscode", "ide ", "neovim", "jetbrains",
            "lm studio", "jan ", "msty ",
            # 開発コンセプト
            "developer tool", "coding assistant", "code completion",
            "code generation", "code editor", "code review",
            "agentic ", "agent framework", "multi-agent", "agent loop",
            "workflow ", "pipeline", "orchestrat",
            "rag ", "retrieval augmented", "vector database", "vector db",
            "knowledge base", "knowledge graph",
            "langchain", "llamaindex", "llama-index", "haystack",
            "autogen", "crewai", "langgraph", "dspy", "pydantic ai",
            "function calling", "tool calling", "structured output", "json mode",
            "prompt engineer", "system prompt", "prompt template",
            # インフラ・デプロイ
            "self-host", "self hosted", "run local", "on-premise",
            "local model", "local llm", "edge ", "on-device",
            "ollama", "llama.cpp", "vllm", "text-generation-inference",
            "triton ", "torchserve",
            "docker", "kubernetes", "k8s",
            "fastapi", "flask", " cli ", "command line interface",
            "automation", "integration", "webhook", "n8n ",
            "browser automation", "web scraping", "playwright",
            # 開発ツール
            "debugg", "logging", "monitoring", "observab",
            "token count", "context manag", "rate limit",
            "streaming ", "async ", "batch processing",
            "fine-tune your", "train your own",
            "claude code", "cursor rules", "claude.md",
        ]
    },
    "business": {
        "label": "ビジネス・業界",
        "emoji": "💼",
        "border": "#e0a040",
        "keywords": [
            # 資金調達
            "funding", "raises $", "raised $", " million", " billion",
            "investment", "investor", "venture capital", " vc ",
            "series a", "series b", "series c", "series d", "series e",
            "seed round", "pre-seed", "bridge round",
            "valuation", "unicorn", "decacorn",
            # M&A・提携
            "acquisition", "acquires", "acquired by", "merger",
            "buys ", "bought by", "takeover", "spinoff",
            "partnership", "joint venture", "strategic alliance",
            # 上場・財務
            "ipo ", "public offering", "nasdaq", "nyse", " stock",
            "revenue", "profit", "quarterly", "earnings", "fiscal",
            "market cap", "valuation",
            # 人事・組織
            "layoff", "laid off", "job cut", "reorg", "restructur",
            "headcount", "workforce reduction",
            "ceo ", "cto ", "coo ", "cpo ", "chief ", "founder ",
            "hire ", "hiring ", "talent",
            # 企業・製品
            "enterprise ", "b2b ", "saas ",
            "market share", "competition ", "competitor",
            "product launch", "launches ", "announces ",
            # 大手テック
            "microsoft", "google ", "amazon web", "apple ",
            "meta ai", "nvidia", "samsung", "huawei", "baidu", "alibaba",
            "salesforce", "oracle", "ibm ",
            "openai", "anthropic", "deepmind", "inflection",
            "cohere", "mistral ai", "stability ai", "runway",
            "character.ai", "perplexity", "pika ", "kling",
            # ビジネストレンド
            "industry report", "market research", "survey ",
            "customer", "enterprise adoption", "commercial",
            "startup", "unicorn", "accelerator", "incubator",
        ]
    },
    "society": {
        "label": "社会・倫理",
        "emoji": "🌍",
        "border": "#e06060",
        "keywords": [
            # 安全・倫理
            "ai safety", "safe ai", "safety of ai",
            "ethics", "ethical ai", "responsible ai",
            "trustworthy", "transparency",
            "explainab", "interpretab", "black box",
            "bias ", "fairness", "discrimination", "stereotype",
            # 規制・法律
            "regulation", "regulate", "regulator",
            " law ", "legal ", "legislation", "bill ",
            "policy ", "government", "congress", "senate",
            "parliament", "white house", "eu ",
            "eu ai act", "gdpr", "ccpa", "executive order",
            "national security", "ban ", "restrict ", "prohibit",
            "compliance", "audit ",
            # 危害・リスク
            "copyright", "intellectual property", "ip theft",
            "plagiarism", "training data",
            "privacy ", "surveillance", "data collection",
            "misinformation", "disinformation", "fake news",
            "deepfake", "synthetic media", "voice clone",
            "hallucination", "confabulation", "factual error",
            "risk ", "danger ", "harm ", "threat ", "concern ",
            "vulnerability", "jailbreak", "prompt injection",
            "adversarial", "poisoning",
            # 社会的影響
            "job loss", "unemployment", "replace worker",
            "automate job", "human worker", "displaced",
            "future of work", "ai impact",
            "education", "student", "cheating", "academic integrity",
            "environment", "energy consumption", "carbon footprint",
            "sustainability", "power usage", "water usage",
            "human rights", "democratic", "election",
            "censorship", "freedom of speech",
            "mental health", "wellbeing", "addiction",
            "inequality", "digital divide",
            "healthcare", "medical ai", "clinical",
            "autonomous weapon", "military ai",
        ]
    },
    "build_ideas": {
        "label": "作ってみた",
        "emoji": "💡",
        "border": "#c8b400",
        "keywords": [
            # Show HN系（高シグナル・重み付き）
            "show hn:", "show hn ",
            # 一人称ビルド
            "i built", "i made ", "i created", "i wrote ",
            "i developed", "i trained", "i fine-tuned",
            "we built", "we made ", "we created", "we developed",
            "i'm building", "we're building",
            "i've been building", "i've been working on",
            "my tool", "my app ", "my project",
            "built a ", "built an ", "made a ", "made an ",
            # 公開・リリース表現
            "just launched", "just released", "just shipped",
            "just open sourced", "just published",
            "introducing my", "announcing my", "releasing my",
            "open sourced my", "released my",
            # プロジェクト種別
            "side project", "weekend project", "hobby project",
            "personal project", "fun project", "for fun",
            " demo ", "prototype", "proof of concept", " poc ",
            "experiment with", "experimenting with",
            # チュートリアル
            "how i ", "how to build", "how i built",
            "step by step", "walkthrough", "tutorial on",
            "getting started with", "beginner guide",
            # クリエイティブAI
            "ai art", "ai music", "ai video", "ai game",
            "ai story", "ai writing", "ai poem",
            "generate images", "generating images",
            "text-to-image", "text to image",
            "text-to-video", "text to video",
            "text-to-speech", "voice synthesis",
            "avatar ", "character ai",
            # アプリ種別
            "chrome extension", "browser extension",
            "mobile app", "ios app", "android app",
            "discord bot", "slack bot", "telegram bot",
            " cli tool", "command line tool",
            "hack ", "hacking with", "built with claude",
            "built with gpt", "built with llm",
            "claude code", "vibe cod",
        ]
    }
}

# ── 高シグナルキーワード（スコア3倍） ────────────────────────────────────────

HIGH_SIGNAL: dict[str, list[str]] = {
    "build_ideas": ["show hn:", "i built", "i made ", "we built",
                    "just launched", "side project", "weekend project"],
    "business":    ["raises $", "raised $", "series a", "series b",
                    "series c", "acquisition", "acquires", "layoff"],
    "society":     ["eu ai act", "ai safety", "regulation", "deepfake",
                    "jailbreak", "copyright", "job loss"],
    "research":    ["benchmark", "arxiv", "rlhf", "dpo ", "finetun"],
    "tools":       ["mcp ", "open source", "langchain", "rag "],
}


# ── 分類関数 ──────────────────────────────────────────────────────────────────

def classify_article(title: str, body_text: Optional[str] = None) -> str:
    """
    タイトル（＋本文先頭）でジャンルをスコアリングして返す。
    タイトルは重み2倍、本文は1倍で評価。
    """
    title_lower = (title or "").lower()
    body_lower  = (body_text or "")[:600].lower()

    # タイトルを2回連結することで重みを2倍に
    text = title_lower + " " + title_lower + " " + body_lower

    scores: dict[str, int] = {g: 0 for g in GENRES}

    for genre_id, info in GENRES.items():
        for kw in info["keywords"]:
            if kw.lower() in text:
                # 高シグナルキーワードは3点、通常は1点
                if kw in HIGH_SIGNAL.get(genre_id, []):
                    scores[genre_id] += 3
                else:
                    scores[genre_id] += 1

    best = max(scores, key=lambda g: scores[g])
    return best if scores[best] > 0 else "research"


def get_genre_info(genre_id: str) -> dict:
    """ジャンルIDからラベル・絵文字等を取得する。"""
    return GENRES.get(genre_id, GENRES["research"])
