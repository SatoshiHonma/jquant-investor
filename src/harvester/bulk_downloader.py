"""
J-Quants V2 API 過去データ一括ダウンロードプログラム (Resumable Bulk Downloader)
指定された期間（例：2017年から本日まで）の全上場銘柄の日次四本値データを自動取得します。
すでに保存済みの日はスキップするため、途中で止まっても即座に再開可能です。
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm

# プロジェクトルートをインポートパスに追加
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.harvester.client import JQuantsClient

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(project_root / "data" / "bulk_download.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


def get_business_days(start_date: str, end_date: str) -> list[str]:
    """
    指定された期間内の平日（月〜金）の日付リストを返す（YYYY-MM-DD形式）。
    ※日本の祝日はAPIが空データを返すため、リクエスト後に自動スキップされます。
    """
    dr = pd.bdate_range(start=start_date, end=end_date)
    return [dt.strftime("%Y-%m-%d") for dt in dr]


def run_bulk_download(start_date: str = "2017-01-01", end_date: str = None):
    """
    過去データの一括ダウンロードを実行する。
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    client = JQuantsClient()
    data_dir = client.data_dir

    logger.info(f"=== J-Quants V2 過去データ一括ダウンロード開始 ===")
    logger.info(f"対象期間: {start_date} ~ {end_date}")
    logger.info(f"データ保存先: {data_dir.resolve()}")

    # 1. 営業日リストの生成
    target_dates = get_business_days(start_date, end_date)
    logger.info(f"生成された対象日数 (平日のみ): {len(target_dates)} 日")

    # 2. すでにダウンロード済みのファイルをチェックして除外 (Resumable)
    dates_to_download = []
    for date in target_dates:
        dt = pd.to_datetime(date)
        year_str = dt.strftime('%Y')
        month_str = dt.strftime('%m')
        save_path = data_dir / "daily_bars" / f"year={year_str}" / f"month={month_str}" / f"{date}.parquet"
        
        if save_path.exists():
            # すでにファイルが存在し、かつ壊れていない（0バイトではない）場合はスキップ
            if save_path.stat().st_size > 0:
                continue
        dates_to_download.append(date)

    total_skipped = len(target_dates) - len(dates_to_download)
    logger.info(f"ダウンロード済みスキップ: {total_skipped} 日")
    logger.info(f"新規ダウンロード対象: {len(dates_to_download)} 日")

    if not dates_to_download:
        logger.info("すべての対象日のデータがすでに存在します。終了します。")
        return

    # 予測時間の算出 (1リクエスト1.1秒待機)
    est_seconds = len(dates_to_download) * 1.1
    est_minutes = est_seconds / 60
    logger.info(f"ダウンロード完了までの予想時間: 約 {est_minutes:.1f} 分")
    logger.info("--------------------------------------------------")

    # 3. ダウンロード実行ループ
    success_count = 0
    fail_count = 0

    for date in tqdm(dates_to_download, desc="Bulk Downloading"):
        dt = pd.to_datetime(date)
        year_str = dt.strftime('%Y')
        month_str = dt.strftime('%m')
        save_path = data_dir / "daily_bars" / f"year={year_str}" / f"month={month_str}" / f"{date}.parquet"

        try:
            # データのフェッチとParquet保存
            df = client.fetch_daily_bars(date)
            
            if df.empty:
                # 祝日や市場休業日などは空データが返ってくる
                logger.info(f"[{date}] データがありません（祝日・休場日の可能性があります）。保存をスキップします。")
                continue

            # 保存ディレクトリの作成
            save_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(save_path, engine="pyarrow", index=False)
            
            success_count += 1
            logger.info(f"[{date}] 取得完了: {len(df)} 件のデータを保存しました -> {save_path.name}")

        except Exception as e:
            fail_count += 1
            logger.error(f"[{date}] 取得失敗: {str(e)}")
            # 連続エラーが起きた場合はAPIキーの期限切れやネットワーク遮断の可能性があるため一時停止
            if fail_count >= 5:
                logger.critical("エラーが5回以上連続したため、安全のためダウンロードを中止します。接続状況を確認してください。")
                break

    logger.info("==================================================")
    logger.info(f"ダウンロード完了！")
    logger.info(f"成功: {success_count} 日分, スキップ: {total_skipped} 日分, 失敗: {fail_count} 日分")


if __name__ == "__main__":
    # J-Quants V2 APIのプラン制限対応:
    # - Freeプラン: 過去2年分のみ取得可能
    # - Lightプラン (Satoshi様の現在のプラン): 過去5年分取得可能（2021-05-18〜本日まで）
    # - Standardプラン: 過去10年分取得可能
    # - Premiumプラン: 全期間取得可能
    
    # デフォルトは Satoshi様のプラン制限（過去5年）に合わせて動的に計算します
    five_years_ago = (datetime.now() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    
    # もし将来 Standard/Premium にアップグレードした場合は、start_date="2017-01-01" などに変更してください。
    run_bulk_download(start_date=five_years_ago)


