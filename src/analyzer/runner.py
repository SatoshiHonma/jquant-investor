import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalysisRunner:
    """
    Geminiが生成した分析用PythonコードをParquetデータに対して実行するクラス。
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", "./data"))

    def load_daily_bars(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        指定された期間の全銘柄の日次データを読み込み、1つのDataFrameに統合する。
        """
        all_files = []
        date_range = pd.date_range(start=start_date, end=end_date)
        
        for dt in date_range:
            year = dt.strftime("%Y")
            month = dt.strftime("%m")
            day = dt.strftime("%Y-%m-%d")
            
            file_path = self.data_dir / "daily_bars" / f"year={year}" / f"month={month}" / f"{day}.parquet"
            if file_path.exists():
                all_files.append(file_path)
        
        if not all_files:
            logger.warning(f"No data files found between {start_date} and {end_date}")
            return pd.DataFrame()
            
        logger.info(f"Loading {len(all_files)} files...")
        dfs = [pd.read_parquet(f) for f in all_files]
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # 型変換の安定化
        if "Date" in combined_df.columns:
            combined_df["Date"] = pd.to_datetime(combined_df["Date"])
        
        return combined_df

    def run_code(self, df: pd.DataFrame, code: str) -> Dict[str, Any]:
        """
        文字列として渡されたPythonコードを実行する。
        
        Args:
            df: 分析対象のDataFrame。コード内では 'df' として参照可能。
            code: Geminiが生成したPythonコード。結果は 'output_df' または 'result' に格納されることを期待。
            
        Returns:
            実行結果を含む辞書。成功時は 'success': True と結果データを含む。
        """
        # 実行環境のセットアップ
        # 組み込み関数を制限しつつ、必要なライブラリ（pandas, numpy）を使えるようにする
        import numpy as np
        
        local_env = {
            'df': df,
            'pd': pd,
            'np': np,
            'output_df': None,
            'result': None
        }
        
        try:
            # コードの実行
            # ※セキュリティ上の懸念がある場合は、将来的にさらに制限をかける
            exec(code, {}, local_env)
            
            return {
                "success": True,
                "output_df": local_env.get("output_df"),
                "result": local_env.get("result"),
                "error": None
            }
        except Exception as e:
            logger.error(f"Error executing AI code: {e}")
            return {
                "success": False,
                "output_df": None,
                "result": None,
                "error": str(e)
            }

if __name__ == "__main__":
    # 簡易的な動作確認
    runner = AnalysisRunner()
    
    # 実際はデータがある日付を指定
    test_df = runner.load_daily_bars("2026-05-15", "2026-05-15")
    
    if not test_df.empty:
        # AIが生成したと仮定したコード
        sample_ai_code = """
# 終値が始値より5%以上高い銘柄を抽出する
output_df = df[df['C'] > df['O'] * 1.05]
result = f"Found {len(output_df)} suspicious stocks."
"""
        res = runner.run_code(test_df, sample_ai_code)
        print(f"Success: {res['success']}")
        print(f"Message: {res['result']}")
        if res['output_df'] is not None:
            print(res['output_df'].head())
