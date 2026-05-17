import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# プロジェクトルートの .env を明示的に読み込む
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

class JQuantsClient:
    """
    J-Quants V2 API Client.
    x-api-keyを用いた認証、ページング制御、およびレートリミット(60回/分)に対応しています。
    """
    BASE_URL = "https://api.jquants.com/v2"

    def __init__(self, api_key: str = None, data_dir: str = None):
        self.api_key = api_key or os.getenv("JQUANTS_API_KEY")
        if not self.api_key:
            raise ValueError("JQUANTS_API_KEY is not set.")
        
        self.headers = {"x-api-key": self.api_key}
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # レートリミット (Lightプラン想定: 60回/分)
        # ページネーションを含め完全に安全に抑えるため、1リクエストごとに 1.5 秒待機する
        self.sleep_duration = 1.5 

    def _request(self, endpoint: str, params: dict = None) -> dict:
        """
        APIエンドポイントにリクエストを送信する。
        429 (Too Many Requests) エラーを検出した場合、指数バックオフで自動でリトライします。
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # 流量制御: API制限を安全に防ぐ
        time.sleep(self.sleep_duration)
        
        retries = 5
        backoff = 60  # 429発生時はまず60秒待機
        
        for attempt in range(retries):
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 429:
                print(f"\n[⚠️ 429 Too Many Requests] API制限に達したか、アクセスブロックを検出しました。")
                print(f"安全のため、{backoff}秒間待機した後にリトライします (試行 {attempt + 1}/{retries})...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)  # 次回の待機時間を2倍にする（最大5分）
                continue
                
            response.raise_for_status()
            return response.json()
            
        raise requests.exceptions.HTTPError("429 Too Many Requests が連続したため、安全のため処理を中止しました。")


    def _fetch_all_pages(self, endpoint: str, params: dict = None) -> pd.DataFrame:
        """ページネーションキーがある限り繰り返しAPIを叩いて全データを結合したDataFrameを返す"""
        if params is None:
            params = {}
        all_data = []
        while True:
            data = self._request(endpoint, params=params)
            
            # V2 APIではデータは 'data' キーに格納されています
            if "data" in data and data["data"]:
                all_data.extend(data["data"])
            elif "message" in data:
                print(f"API Message: {data['message']}")
            
            pagination_key = data.get("pagination_key")
            if not pagination_key:
                break
                
            # 次のページを取得するため、pagination_key をパラメータにセット
            params["pagination_key"] = pagination_key

        return pd.DataFrame(all_data)

    def fetch_daily_bars(self, date: str) -> pd.DataFrame:
        """
        指定した日付の全銘柄の四本値データを取得し、DataFrameとして返す。
        
        Args:
            date (str): YYYYMMDD または YYYY-MM-DD 形式の日付
        """
        date_str = date.replace("-", "")
        return self._fetch_all_pages("/equities/bars/daily", {"date": date_str})

    def save_daily_bars_to_parquet(self, date: str):
        """
        指定した日付の四本値データを取得し、Parquet形式で保存する。
        保存先: {data_dir}/daily_bars/year=YYYY/month=MM/YYYY-MM-DD.parquet
        """
        df = self.fetch_daily_bars(date)
        if df.empty:
            return
        self._save_to_daily_partition(df, date, "daily_bars")

    def fetch_master(self) -> pd.DataFrame:
        """最新の銘柄マスタ（全上場銘柄）を取得する。"""
        return self._fetch_all_pages("/equities/master")

    def save_master_to_parquet(self):
        """最新の銘柄マスタを取得し、単一のマスタファイルとして保存する。"""
        print("Fetching equities master list...")
        df = self.fetch_master()
        if df.empty:
            print("No master data found.")
            return
        save_path = self.data_dir / "equities_master.parquet"
        df.to_parquet(save_path, engine="pyarrow", index=False)
        print(f"Saved {len(df)} records to {save_path}")

    def fetch_fins_summary(self, date: str) -> pd.DataFrame:
        """指定した開示日の財務情報サマリーを取得する。"""
        date_str = date.replace("-", "")
        return self._fetch_all_pages("/fins/summary", {"date": date_str})

    def save_fins_summary_to_parquet(self, date: str):
        """指定した開示日の財務サマリーを取得し、Parquet形式で保存する。"""
        df = self.fetch_fins_summary(date)
        if df.empty:
            return
        self._save_to_daily_partition(df, date, "fins_summary")

    def fetch_investor_types(self, date: str) -> pd.DataFrame:
        """指定した公開日/週の投資部門別情報を取得する。"""
        date_str = date.replace("-", "")
        return self._fetch_all_pages("/equities/investor-types", {"date": date_str})

    def save_investor_types_to_parquet(self, date: str):
        """指定した日の投資部門別情報を取得し、Parquet形式で保存する。"""
        df = self.fetch_investor_types(date)
        if df.empty:
            return
        self._save_to_daily_partition(df, date, "investor_types")

    def fetch_topix_bars(self, date: str) -> pd.DataFrame:
        """指定した日のTOPIX指数四本値データを取得する。"""
        date_str = date.replace("-", "")
        return self._fetch_all_pages("/indices/bars/daily/topix", {"date": date_str})

    def save_topix_bars_to_parquet(self, date: str):
        """指定した日のTOPIX指数四本値をParquet形式で保存する。"""
        df = self.fetch_topix_bars(date)
        if df.empty:
            return
        self._save_to_daily_partition(df, date, "topix_bars")

    def fetch_earnings_calendar(self) -> pd.DataFrame:
        """決算発表予定日スケジュールを取得する。"""
        return self._fetch_all_pages("/equities/earnings-calendar")

    def save_earnings_calendar_to_parquet(self):
        """決算発表予定日スケジュールを単一のファイルとして保存する。"""
        print("Fetching earnings calendar...")
        df = self.fetch_earnings_calendar()
        if df.empty:
            print("No calendar data found.")
            return
        save_path = self.data_dir / "earnings_calendar.parquet"
        df.to_parquet(save_path, engine="pyarrow", index=False)
        print(f"Saved {len(df)} records to {save_path}")

    def _save_to_daily_partition(self, df: pd.DataFrame, date: str, folder_name: str):
        """日付ごとのディレクトリ階層（year=YYYY/month=MM）にParquetファイルを保存する共通ヘルパー"""
        dt = pd.to_datetime(date)
        year_str = dt.strftime('%Y')
        month_str = dt.strftime('%m')
        date_str = dt.strftime('%Y-%m-%d')
        
        save_dir = self.data_dir / folder_name / f"year={year_str}" / f"month={month_str}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        save_path = save_dir / f"{date_str}.parquet"
        df.to_parquet(save_path, engine="pyarrow", index=False)
        print(f"Saved {len(df)} records to {save_path}")

if __name__ == "__main__":
    client = JQuantsClient()

