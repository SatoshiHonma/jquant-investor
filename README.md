# J-Quants AI Investor Agent

J-Quants V2 APIを活用し、Gemini 1.5 Pro/Flashを搭載した自律進化型AIが投資戦略の立案から実行（分析コード生成）までを行うプロジェクトです。

## 📁 ディレクトリ構造

```text
/jquants-investor
├── config/
│   ├── settings.yaml     # 取得対象銘柄、リスク許容度などの静的設定
│   └── schema.json       # J-Quants V2の正確なスキーマ定義（Gemini幻覚防止用）
├── src/
│   ├── harvester/        # 【データ収集】API接続・Parquet保存
│   ├── analyzer/         # 【分析実行】AI生成コードのサンドボックス実行
│   └── agent/            # 【推論・意思決定】Geminiによる戦略立案ループ
├── .env                  # 機密情報（Git管理対象外）
├── .env.example          # 環境変数テンプレート
├── Dockerfile            # 本番環境用マルチステージビルド
└── docker-compose.yml    # ボリュームマウント・常時起動定義
```

## 🚀 セットアップ (Dev環境)

### 1. 環境構築
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 設定
`.env.example` をコピーして `.env` を作成し、J-QuantsのAPIキーを入力してください。

### 3. 動作確認
```bash
# 日次四本値の取得とParquet保存のテスト
python -c "from src.harvester.client import JQuantsClient; JQuantsClient().save_daily_bars_to_parquet('2026-05-15')"
```

## 📊 過去データ一括ダウンロード & 日本株データベース要塞化計画

J-Quants V2 API をフル活用し、ローカル環境（ホスト側）に超高速・高圧縮なParquet形式の「日本株データベース」を構築します。

### 1. 過去データ一括ダウンロード (Bulk Downloader)

安全かつ自動で、Satoshi様のプラン上限である **過去5年分 (Lightプランの制限)** の全上場銘柄（約4,000社）の日次株価（四本値・調整株価・出来高）を一括ダウンロードします。

#### ✨ 特徴
- **祝日・週末の自動スキップ**: API枠の無駄な消費を自動で防ぎます。
- **完全レジューム機能**: 途中でネットワークが切れたりCtrl+Cで停止しても、再実行時に自動的にダウンロード済みのファイルをスキップして続きから自動再開します。
- **超軽量Parquet形式**: カラム指向の超高圧縮バイナリ形式で保存するため、5年分の全日本株式データでも **約150MB〜250MB程度** にスマートに収まります。

#### 🚀 実行方法 (Docker経由)
```bash
docker compose exec agent python src/harvester/bulk_downloader.py
```
* **データの保存先**: ホスト（ローカル）の `./data/daily_bars/year=YYYY/month=MM/YYYY-MM-DD.parquet` に自動で同期され、Jupyter Notebookなどから直接読み込めます。

---

### 2. 🗄️ 今後ダウンロード可能な主要データ（Lightプラン範囲内）

Satoshi様のLightプラン（過去5年制限）の範囲内で、さらに投資分析を強力にする以下のデータを追加ダウンロード可能です。

| データセット | V2 APIエンドポイント | 分析への活用例 |
| :--- | :--- | :--- |
| **① 銘柄マスタ情報** | `/v2/equities/master` | 4,000社の「業種（33業種）」「市場区分（プライム等）」を取得。株価と結合して**「IT企業の株だけ抽出」「グロース株だけ分析」**が可能に！ |
| **② 財務情報サマリー** | `/v2/equities/statements` | 過去5年分の四半期決算（売上、営業利益、EPS、BPS、来期予想など）を取得。株価と結合してリアルタイムな **「PER」「PBR」** などの割安指標を計算可能！ |
| **③ 投資部門別情報** | `/v2/equities/investor-types` | 海外投資家や個人投資家の週次売買動向を取得。**相場の巨大トレンドを生み出す外国人マネーの買い越し・売り越しトレンド**を分析！ |
| **④ TOPIX指数四本値** | `/v2/indices/bars/daily/topix` | 日本市場を代表するTOPIXの日次株価を取得。個別株価と並べて**「市場全体より強い銘柄（相対的強さ）」**をスクリーニング！ |
| **⑤ 決算発表予定日** | `/v2/equities/earnings-calendar` | 決算発表のスケジュールを取得。**「決算直前のリスク回避」**や**「決算プレイ（急変動狙い）」**の自動スケジュール判定に！ |

---


## 🛠 今後のロードマップ
- [ ] **Analyzer Runner**: AIが生成したPandasコードをParquetデータに対し実行する環境の構築。
- [ ] **Agent Logic**: Gemini 1.5 Proによるマクロ仮説立案とコード生成。
- [ ] **Self-Healing Loop**: 毎日の「答え合わせ」によるプロンプトの自動改善機能。
- [ ] **Discord Notification**: トレード提案やシステム異常のスマホ通知。
