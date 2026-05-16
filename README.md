# J-Quants AI Investor Agent

J-Quants V2 APIを活用し、Gemini 1.5 Pro/Flashを搭載した自律進化型AIが投資戦略の立案から実行（分析コード生成）までを行うプロジェクトです。

## 🌟 プロジェクトの設計思想

本プロジェクトは、SRE（Site Reliability Engineering）の標準に基づき、開発効率と安定運用の両立を目指しています。

### 1. 開発・デプロイ環境の分離 (Dev/Prod)
- **開発環境 (Dev)**: ローカルPC（VS Code + Jupyter）でサンドボックス実験とコード実装。
- **本番環境 (Prod)**: 常時稼働Windows上のDockerコンテナ。Google Drive (5TB) を `/app/data` にマウントし、Parquetデータレイクを構築。

### 2. 認証・機密情報の管理
- APIキー等の機密情報は `.env` ファイルで一括管理し、GitHubには `.env.example` のみを配置。
- J-Quants V2の `x-api-key` 固定ヘッダー方式を採用。

### 3. データ蓄積レイヤー (Harvester)
- J-Quants V2 APIのレートリミット（60件/分）を厳守したスロットリング。
- `pagination_key` を用いた自動ページネーション制御。
- Apache Parquet形式による効率的なパーティショニング保存。

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

## 🛠 今後のロードマップ
- [ ] **Analyzer Runner**: AIが生成したPandasコードをParquetデータに対し実行する環境の構築。
- [ ] **Agent Logic**: Gemini 1.5 Proによるマクロ仮説立案とコード生成。
- [ ] **Self-Healing Loop**: 毎日の「答え合わせ」によるプロンプトの自動改善機能。
- [ ] **Discord Notification**: トレード提案やシステム異常のスマホ通知。
