import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import logging

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
        for dt in pd.date_range(start=start_date, end=end_date):
            file_path = (
                self.data_dir
                / "daily_bars"
                / f"year={dt.strftime('%Y')}"
                / f"month={dt.strftime('%m')}"
                / f"{dt.strftime('%Y-%m-%d')}.parquet"
            )
            if file_path.exists():
                all_files.append(file_path)

        if not all_files:
            logger.warning(f"No data files found between {start_date} and {end_date}")
            return pd.DataFrame()

        logger.info(f"Loading {len(all_files)} files...")
        df = pd.concat([pd.read_parquet(f) for f in all_files], ignore_index=True)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        return df

    def run_code(self, df: pd.DataFrame, code: str, extra_vars: dict = None) -> Dict[str, Any]:
        """
        文字列として渡されたPythonコードを実行する。

        Args:
            df:         分析対象のDataFrame（コード内では 'df' として参照）
            code:       Geminiが生成したPythonコード
            extra_vars: 追加で渡す変数（例: 前回の output_df を引き継ぐ場合）

        Returns:
            {"success": bool, "output_df": DataFrame|None, "result": str|None, "error": str|None}
        """
        import numpy as np

        local_env = {'df': df, 'pd': pd, 'np': np, 'output_df': None, 'result': None}
        if extra_vars:
            local_env.update(extra_vars)

        try:
            exec(code, {}, local_env)
            return {
                "success": True,
                "output_df": local_env.get("output_df"),
                "result": local_env.get("result"),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error executing AI code: {e}")
            return {"success": False, "output_df": None, "result": None, "error": str(e)}
