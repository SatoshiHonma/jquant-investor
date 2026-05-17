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


    def fetch_daily_bars(self, date: str) -> pd.DataFrame:
        """
        指定した日付の全銘柄の四本値データを取得し、DataFrameとして返す。
        ページネーションキーが含まれている場合は自動でループ処理を行う。
        
        Args:
            date (str): YYYYMMDD または YYYY-MM-DD 形式の日付
        """
        endpoint = "/equities/bars/daily"
        # YYYYMMDD形式に整形（必要に応じて）
        date_str = date.replace("-", "")
        params = {"date": date_str}
        
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

        df = pd.DataFrame(all_data)
        return df

    def save_daily_bars_to_parquet(self, date: str):
        """
        指定した日付の四本値データを取得し、Parquet形式で保存する。
        保存先: {data_dir}/daily_bars/year=YYYY/month=MM/YYYY-MM-DD.parquet
        """
        print(f"Fetching data for {date}...")
        df = self.fetch_daily_bars(date)
        
        if df.empty:
            print(f"No data found for {date}.")
            return
            
        # Parquet形式への保存 (パーティショニング)
        # date は YYYYMMDD または YYYY-MM-DD を想定し、YYYY-MM-DD に統一して扱う
        dt = pd.to_datetime(date)
        year_str = dt.strftime('%Y')
        month_str = dt.strftime('%m')
        date_str = dt.strftime('%Y-%m-%d')
        
        save_dir = self.data_dir / "daily_bars" / f"year={year_str}" / f"month={month_str}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        save_path = save_dir / f"{date_str}.parquet"
        
        # engine="fastparquet" または "pyarrow" が使用可能
        df.to_parquet(save_path, engine="pyarrow", index=False)
        print(f"Saved {len(df)} records to {save_path}")

if __name__ == "__main__":
    # テスト実行用 (今日の日付で取得を試みる例、実際は営業日を指定する)
    client = JQuantsClient()
    # client.save_daily_bars_to_parquet("2023-10-02")
