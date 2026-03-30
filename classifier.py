"""
キーワードルールベースのジャンル分類器
各ジャンルのキーワードリストに対してスコアリングし、最も一致するジャンルを返す。
"""

from typing import Optional

# ── ジャンル定義 ────────────────────────────────────────────────────────────

GENRES: dict = {
    "storage_tech": {
        "label": "蓄電技術",
        "emoji": "🔋",
        "border": "#6e8efb",
        "keywords": [
            # バッテリーシステム
            "bess", "battery energy storage", "grid-scale battery",
            "battery storage system", "energy storage system", "ess ",
            "utility-scale storage", "large-scale battery",
            # セル化学
            "lfp", "lithium iron phosphate", "nmc ", "nmca", "nca ",
            "sodium-ion", "sodium ion", "solid state battery", "all-solid",
            "solid-state", "全固体", "ナトリウムイオン",
            "vanadium redox", "flow battery", "redox flow",
            "lead-acid", "zinc", "iron-air", "hydrogen storage",
            # 日本語
            "蓄電池", "系統用蓄電", "リチウムイオン", "リン酸鉄リチウム",
            "レドックスフロー", "フロー電池",
            # 長期蓄電・揚水
            "long duration", "long-duration storage", "ldes",
            "pumped hydro", "pumped storage", "揚水発電", "揚水",
            "compressed air", "caes",
            # コンポーネント・制御
            "pcs ", "power conversion system", "bms ", "battery management",
            "inverter", "dc-ac", "ac-dc",
            # 性能指標
            "round-trip efficiency", "cycle life", "state of charge",
            "soc ", "soh ", "depth of discharge", "dod ",
            "energy density", "power density", "c-rate",
            "thermal runaway", "fire suppression", "thermal management",
            # 製品名
            "megapack", "powerpack", "powerwall",
            # V2G・第二の用途
            "v2g ", "vehicle to grid", "vehicle-to-grid",
            "second life battery", "second-life battery",
        ]
    },
    "grid_ops": {
        "label": "系統運用",
        "emoji": "⚡",
        "border": "#3ab8c0",
        "keywords": [
            # アンシラリーサービス（英語）
            "ancillary service", "ancillary services",
            "frequency regulation", "frequency response", "frequency control",
            "frequency containment", "frequency deviation",
            "fcr ", "ffr ", "drr ", "dcr ", "efr ",
            "primary response", "secondary response", "tertiary response",
            "primary reserve", "secondary reserve", "tertiary reserve",
            "synthetic inertia", "virtual inertia", "grid inertia",
            "fast frequency", "dynamic containment",
            # 需給調整（日本語）
            "需給調整", "周波数調整", "調整力",
            "一次調整力", "二次調整力", "三次調整力",
            "アンシラリー", "慣性力",
            # 系統安定化
            "grid stabilization", "grid stability", "grid balancing",
            "grid services", "grid integration", "grid support",
            "系統安定", "系統運用", "系統安定化", "系統制御",
            "電力需給", "需給バランス",
            # デマンドレスポンス
            "demand response", "demand flexibility", "demand side",
            "load shifting", "peak shaving", "peak demand",
            # 出力制御
            "curtailment", "output curtailment", "renewable curtailment",
            "出力制御", "出力抑制",
            # 系統接続
            "ノンファーム", "non-firm connection", "ノンファーム型接続",
            "系統混雑", "送電混雑", "潮流", "連系線",
            # 系統運用者
            "occto", "広域機関",
            "tso ", "dso ", "iso ", "system operator",
            # VPP・アグリゲーション
            "vpp", "virtual power plant", "仮想発電所",
            "aggregator", "アグリゲーター", "リソースアグリゲーター",
        ]
    },
    "market_policy": {
        "label": "市場・制度",
        "emoji": "📋",
        "border": "#e0a040",
        "keywords": [
            # FIT / FIP
            "fip ", "feed-in premium", "フィード・イン・プレミアム",
            "fip転", "fip制度", "fit制度", "固定価格買取",
            "fit ", "feed-in tariff",
            "premium payment", "reference price", "基準価格",
            "balancing group", "バランシンググループ", "インバランス精算",
            # 電力市場
            "容量市場", "capacity market", "capacity auction",
            "需給調整市場",
            "spot market", "スポット市場", "jepx",
            "インバランス", "imbalance", "imbalance settlement",
            "kw市場", "kw価値", "kw value",
            "電力市場", "power market", "electricity market",
            "先渡市場", "先物市場",
            # 規制・制度
            "regulation ", "regulatory reform", "規制改正",
            "再エネ賦課金", "renewable surcharge",
            "系統マスタープラン", "grid master plan",
            "電源入札", "公募入札", "renewable auction",
            "ferc ", "cpuc ", "eu ai act",
            # 目標・政策
            "carbon market", "カーボンクレジット", "j-credit",
            "再エネ特措法", "省エネ法", "電気事業法",
            "gx ", "グリーントランスフォーメーション",
            "脱炭素", "carbon neutral", "net zero", "net-zero",
            "renewable target", "再エネ目標",
            "2030年", "2050年",
            # 欧米制度
            "entso", "eu taxonomy", "red ii", "red iii",
            "ira ", "inflation reduction act",
        ]
    },
    "project": {
        "label": "プロジェクト",
        "emoji": "🏗️",
        "border": "#80c080",
        "keywords": [
            # プロジェクトライフサイクル
            "着工", "竣工", "稼働", "運転開始", "商業運転",
            "commissioned", "operational", "went online", "came online",
            "construction begins", "ground-breaking", "建設中",
            # 規模・容量
            "mw battery", "mwh battery", "gwh battery",
            "mw bess", "mwh bess",
            "mw storage", "mwh storage",
            # 入札・調達
            "入札", "公募", "落札", "応募", "選定",
            "procurement", "tender ", "bid ", "contract award",
            "epc ", "turnkey",
            # 実証・パイロット
            "pilot project", "pilot program",
            "demonstration project", "demo project",
            "実証", "実証事業", "実証試験", "実証実験",
            "実証プロジェクト",
            # ハイブリッド・共設置
            "co-located", "co-location", "hybrid project",
            "solar-plus-storage", "solar plus storage",
            "wind-plus-storage", "wind plus storage",
            "再エネ＋蓄電", "太陽光＋蓄電",
            "再エネ蓄電",
            # 特定プロジェクト形態
            "grid-connected project", "utility-scale project",
            "standalone storage", "独立型蓄電",
        ]
    },
    "business": {
        "label": "ビジネス",
        "emoji": "💼",
        "border": "#e06060",
        "keywords": [
            # 資金調達
            "funding", "raises $", "raised $", " million", " billion",
            "investment", "investor", "venture capital",
            "series a", "series b", "series c", "series d",
            "financing", "project finance", "debt financing",
            "グリーンボンド", "green bond", "出資",
            # M&A・提携
            "acquisition", "acquires", "merger", "takeover",
            "partnership", "joint venture", "提携", "合弁", "買収",
            # 上場・財務
            "ipo ", "stock", "revenue", "profit", "earnings",
            "market share", "valuation",
            # 企業名（蓄電池主要プレイヤー）
            "tesla ", "fluence", "wärtsilä", "wartsila",
            "catl ", "byd ", "samsung sdi", "lg energy", "panasonic",
            "mitsubishi", "toshiba", "hitachi", "nec ", "ngk ",
            "eneos", "jera ", "tepco", "関西電力", "中部電力", "九州電力",
            "東京電力", "関電", "softbank energy",
            "enel ", "abb ", "siemens", "schneider",
            "invinity", "form energy", "ambri", "ess inc",
            # サプライチェーン
            "lithium supply", "cobalt", "nickel supply",
            "supply chain", "サプライチェーン",
            "cathode material", "anode material", "electrolyte",
            "gigafactory", "ギガファクトリー", "電池工場",
            # 人事
            "layoff", "ceo ", "cto ", "chief executive",
        ]
    },
    "overseas": {
        "label": "海外動向",
        "emoji": "🌍",
        "border": "#c8b400",
        "keywords": [
            # オーストラリア（BESS先進市場）
            "australia", "australian", "aemo ", "hornsdale",
            "neoen", "victoria big battery", "waratah super battery",
            "nem ", "national electricity market",
            "fcas ", "contingency fcas", "regulation fcas",
            "big battery", "grid battery australia",
            # イギリス
            "great britain", "national grid eso", "neso ",
            "balancing mechanism", " bm ", "bmu ",
            "firm frequency response", "enhanced frequency response",
            "dynamic containment", "dynamic moderation",
            "capacity market uk", "uk storage",
            # アメリカ
            "united states storage", "us storage",
            "caiso ", "pjm ", "ercot ", "miso ", "nyiso",
            "ferc order", "ferc rule",
            "california storage", "texas grid",
            "inflation reduction act", "ira storage",
            # ヨーロッパ
            "european storage", "eu storage",
            "entso-e", "germany storage", "deutschland",
            "france storage", "spain storage",
            "nordic flexibility", "flexibility market europe",
            # アジア
            "china battery market", "south korea battery",
            "india storage market", "taiwan grid storage",
            # 海外制度・市場設計
            "capacity mechanism", "revenue stacking",
            "multiple revenue streams", "co-optimisation",
        ]
    },
}

# ── 高シグナルキーワード（スコア3倍） ────────────────────────────────────────

HIGH_SIGNAL: dict[str, list[str]] = {
    "storage_tech":   ["bess", "battery energy storage", "蓄電池", "lfp", "megapack",
                       "flow battery", "long-duration storage", "pumped hydro"],
    "grid_ops":       ["ancillary service", "ancillary services", "frequency regulation",
                       "需給調整", "出力制御", "系統安定", "virtual power plant", "vpp"],
    "market_policy":  ["fip ", "feed-in premium", "fip転", "容量市場", "jepx",
                       "需給調整市場", "feed-in tariff", "inflation reduction act"],
    "project":        ["commissioned", "mw battery", "mwh battery", "実証事業",
                       "co-located", "solar-plus-storage"],
    "business":       ["raises $", "series a", "series b", "acquisition", "acquires",
                       "catl ", "fluence", "gigafactory"],
    "overseas":       ["aemo ", "ferc order", "caiso ", "national grid eso",
                       "hornsdale", "fcas "],
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
    return best if scores[best] > 0 else "storage_tech"


def get_genre_info(genre_id: str) -> dict:
    """ジャンルIDからラベル・絵文字等を取得する。"""
    return GENRES.get(genre_id, GENRES["storage_tech"])
