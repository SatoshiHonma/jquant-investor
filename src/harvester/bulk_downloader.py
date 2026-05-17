"""
J-Quants V2 API 総合過去データ一括ダウンロードプログラム (Comprehensive Resumable Bulk Downloader)
Satoshi様のLightプラン（過去5年制限）で取得可能なすべての日本株データセットを一挙にローカルParquetデータベースへ集約します。
"""

import os
import sys
import logging
import argparse
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
    """指定された期間内の平日（月〜金）の日付リストを返す（YYYY-MM-DD形式）"""
    dr = pd.bdate_range(start=start_date, end=end_date)
    return [dt.strftime("%Y-%m-%d") for dt in dr]


def download_daily_dataset(client: JQuantsClient, folder_name: str, fetch_func, start_date: str, end_date: str):
    """日次データを日付ごとにループして安全にダウンロードし、Parquet保存する共通オーケストレーター (Resumable)"""
    logger.info(f"\n==================================================")
    logger.info(f"▶ [{folder_name}] の一括ダウンロードを開始します...")
    logger.info(f"対象期間: {start_date} ~ {end_date}")
    
    target_dates = get_business_days(start_date, end_date)
    data_dir = client.data_dir
    
    # 1. すでに保存済みのファイルを検出してスキップ対象にする (Resumable)
    dates_to_download = []
    for date in target_dates:
        dt = pd.to_datetime(date)
        year_str = dt.strftime('%Y')
        month_str = dt.strftime('%m')
        save_path = data_dir / folder_name / f"year={year_str}" / f"month={month_str}" / f"{date}.parquet"
        
        if save_path.exists() and save_path.stat().st_size > 0:
            continue
        dates_to_download.append(date)
        
    total_skipped = len(target_dates) - len(dates_to_download)
    logger.info(f"[{folder_name}] 既にダウンロード済みスキップ: {total_skipped} 日分")
    logger.info(f"[{folder_name}] 新規ダウンロード対象: {len(dates_to_download)} 日分")
    
    if not dates_to_download:
        logger.info(f"[{folder_name}] すべての対象日のデータがすでに存在します。")
        return
        
    # 予測時間
    est_seconds = len(dates_to_download) * 1.1
    logger.info(f"[{folder_name}] 予想所要時間: 約 {est_seconds / 60:.1f} 分")
    
    # 2. ダウンロード実行ループ
    success_count = 0
    fail_count = 0
    consecutive_fails = 0
    
    for date in tqdm(dates_to_download, desc=f"Downloading {folder_name}"):
        try:
            df = fetch_func(date)
            if df.empty:
                logger.debug(f"[{date}] 空データのため保存をスキップします。")
                continue
                
            client._save_to_daily_partition(df, date, folder_name)
            success_count += 1
            consecutive_fails = 0  # 成功したため連続エラーをリセット
        except Exception as e:
            fail_count += 1
            consecutive_fails += 1
            logger.error(f"[{date}] 取得失敗: {str(e)}")
            
            if consecutive_fails >= 5:
                logger.critical(f"[{folder_name}] エラーが5回以上連続したため安全のため処理を一時中断します。")
                break
                
    logger.info(f"✔ [{folder_name}] 完了！ 成功: {success_count}日分, 失敗: {fail_count}日分")


def main():
    parser = argparse.ArgumentParser(description="J-Quants V2 総合過去データ一括ダウンロードプログラム")
    parser.add_argument(
        "--target",
        type=str,
        default="all",
        choices=["all", "master", "daily_bars", "fins_summary", "investor_types", "topix_bars", "earnings_calendar"],
        help="ダウンロードする対象のデータセット (デフォルト: all)"
    )
    args = parser.parse_args()

    # J-Quants V2 APIのプラン制限（Satoshi様のLightプラン: 過去5年）に合わせて動的計算
    five_years_ago = (datetime.now() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    client = JQuantsClient()
    target = args.target

    logger.info("==================================================")
    logger.info("  J-Quants V2 データベース構築 & ダウンローダー開始")
    logger.info("==================================================")

    # 1. 銘柄マスタ (TSE Master) のダウンロード
    if target in ["all", "master"]:
        try:
            client.save_master_to_parquet()
        except Exception as e:
            logger.error(f"銘柄マスタの取得に失敗しました: {e}")

    # 2. 決算発表スケジュールカレンダーのダウンロード
    if target in ["all", "earnings_calendar"]:
        try:
            client.save_earnings_calendar_to_parquet()
        except Exception as e:
            logger.error(f"決算スケジュールの取得に失敗しました: {e}")

    # 3. 日次TOPIX指数のダウンロード
    if target in ["all", "topix_bars"]:
        download_daily_dataset(
            client=client,
            folder_name="topix_bars",
            fetch_func=client.fetch_topix_bars,
            start_date=five_years_ago,
            end_date=today
        )

    # 4. 決算サマリー数値 (財務短信データ) のダウンロード
    if target in ["all", "fins_summary"]:
        download_daily_dataset(
            client=client,
            folder_name="fins_summary",
            fetch_func=client.fetch_fins_summary,
            start_date=five_years_ago,
            end_date=today
        )

    # 5. 投資部門別売買動向のダウンロード
    if target in ["all", "investor_types"]:
        download_daily_dataset(
            client=client,
            folder_name="investor_types",
            fetch_func=client.fetch_investor_types,
            start_date=five_years_ago,
            end_date=today
        )

    # 6. 日次株価四本値 (最重要・最長データ) のダウンロード
    if target in ["all", "daily_bars"]:
        download_daily_dataset(
            client=client,
            folder_name="daily_bars",
            fetch_func=client.fetch_daily_bars,
            start_date=five_years_ago,
            end_date=today
        )

    logger.info("\n==================================================")
    logger.info("🎉 すべての指定ターゲットデータのダウンロード処理が完了しました！")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
