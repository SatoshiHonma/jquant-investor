"""
Session: 1つの分析テーマ = 1つのディスク上のフォルダ。
会話履歴、計算結果（artifacts）、データ状態を一元管理する。
カーネル再起動や翌日の再開でも、全てが復元される。
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd

from src.agent.core import GeminiClient
from src.analyzer.runner import AnalysisRunner

logger = logging.getLogger(__name__)


class Session:
    """
    1つの分析テーマ（スイング、マクロなど）を管理するセッション。

    使い方:
        session = Session("swing_20260517", data_range=("2024-05-13", "2024-05-15"))
        session.chat("大陽線の銘柄を出来高順で。")
        session.chat("その中から終値2000円以下に絞って。")
        session.latest_output_df  # 最新の計算結果

    翌日の再開:
        session = Session("swing_20260517")  # ← 全部復元される
    """

    def __init__(
        self,
        name: str,
        data_range: tuple[str, str] | None = None,
        data_dir: str = "./data",
        persona: str = "",
    ):
        self.name = name
        self.data_dir = Path(data_dir)
        self.session_dir = self.data_dir / "sessions" / name
        self.artifacts_dir = self.session_dir / "artifacts"
        self.conversation_file = self.session_dir / "conversation.json"
        self.state_file = self.session_dir / "state.json"

        # ディレクトリ作成
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # 外部コンポーネント
        self.runner = AnalysisRunner(data_dir=str(self.data_dir))
        self.gemini = GeminiClient(persona=persona)

        # 内部状態
        self.conversation: list[dict] = []
        self.df: Optional[pd.DataFrame] = None
        self._output_df: Optional[pd.DataFrame] = None
        self._step: int = 0

        # 復元 or 新規初期化
        self._restore_state()
        if data_range and self.df is None:
            self._load_data(data_range[0], data_range[1])

    # ─── Public API ─────────────────────────────────────────

    @property
    def latest_output_df(self) -> Optional[pd.DataFrame]:
        """最新の計算結果を返す（自分のコードでも使える）"""
        return self._output_df

    def chat(self, message: str) -> str:
        """
        AIにメッセージを送信し、コードがあれば実行し、結果を保存する。
        全てディスクに永続化される。
        """
        # 1. AIに送るコンテキストを構築（データの状態を教える）
        data_context = self._build_data_context()
        enriched_message = f"{data_context}\n\nユーザーの指示:\n{message}"

        # 2. 会話履歴にユーザーメッセージを追加
        self.conversation.append({
            "role": "user",
            "parts": enriched_message,
            "timestamp": datetime.now().isoformat(),
        })

        # 3. Gemini API呼び出し
        reply = self.gemini.generate(self.conversation)
        self.conversation.append({
            "role": "model",
            "parts": reply,
            "timestamp": datetime.now().isoformat(),
        })

        # 4. コード抽出と実行
        import re
        code_blocks = re.findall(r"```python\n(.*?)\n```", reply, re.DOTALL)
        exec_result = None

        if code_blocks:
            code = code_blocks[0]
            exec_result = self.runner.run_code(
                self.df,
                code,
                extra_vars={"output_df": self._output_df},
            )

            if exec_result.get("success") and exec_result.get("output_df") is not None:
                self._step += 1
                self._output_df = exec_result["output_df"]
                self._save_artifact(self._output_df, self._step)

        # 5. 全て永続化
        self._save_conversation()
        self._save_state()

        return reply, exec_result

    def clear(self):
        """セッションの会話と計算結果をリセットする（データは残す）"""
        self.conversation = []
        self._output_df = None
        self._step = 0
        self._save_conversation()
        self._save_state()

    def list_artifacts(self) -> list[str]:
        """保存されている計算結果（artifact）の一覧を返す"""
        return sorted([f.name for f in self.artifacts_dir.glob("*.parquet")])

    def load_artifact(self, step: int) -> pd.DataFrame:
        """指定したステップの計算結果を読み込む"""
        path = self.artifacts_dir / f"step_{step:03d}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        raise FileNotFoundError(f"Artifact step_{step:03d}.parquet not found.")

    # ─── Private Methods ────────────────────────────────────

    def _load_data(self, start_date: str, end_date: str):
        """Parquetデータを読み込んでセッションに紐付ける"""
        self.df = self.runner.load_daily_bars(start_date, end_date)
        logger.info(f"Session '{self.name}': Loaded {len(self.df)} records ({start_date} ~ {end_date})")
        self._save_state()

    def _build_data_context(self) -> str:
        """AIに毎回送る「今のデータの状態」の要約"""
        lines = [f"[Session: {self.name} | {datetime.now().strftime('%Y-%m-%d %H:%M')}]"]

        if self.df is not None:
            lines.append(f"ベースデータ (df): {len(self.df)} 行 × {len(self.df.columns)} 列")
            lines.append(f"カラム: {list(self.df.columns)}")

        if self._output_df is not None:
            lines.append(f"\n前回の output_df (step {self._step}): {len(self._output_df)} 行 × {len(self._output_df.columns)} 列")
            lines.append(f"カラム: {list(self._output_df.columns)}")
            lines.append(f"先頭5行:\n{self._output_df.head().to_string()}")
        else:
            lines.append("\noutput_df: まだ計算結果はありません。")

        return "\n".join(lines)

    def _save_artifact(self, df: pd.DataFrame, step: int):
        """計算結果をParquetとしてディスクに永続化する"""
        path = self.artifacts_dir / f"step_{step:03d}.parquet"
        df.to_parquet(path, index=False)
        logger.info(f"Saved artifact: {path.name} ({len(df)} rows)")

    def _save_conversation(self):
        with open(self.conversation_file, "w", encoding="utf-8") as f:
            json.dump(self.conversation, f, ensure_ascii=False, indent=2)

    def _save_state(self):
        state = {
            "name": self.name,
            "step": self._step,
            "data_rows": len(self.df) if self.df is not None else 0,
            "data_columns": list(self.df.columns) if self.df is not None else [],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _restore_state(self):
        """既存セッションの復元"""
        # 会話の復元
        if self.conversation_file.exists():
            with open(self.conversation_file, "r", encoding="utf-8") as f:
                self.conversation = json.load(f)
            logger.info(f"Session '{self.name}': Restored {len(self.conversation)} messages.")

        # 状態の復元
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            self._step = state.get("step", 0)

        # 最新 artifact の復元
        artifacts = sorted(self.artifacts_dir.glob("*.parquet"))
        if artifacts:
            self._output_df = pd.read_parquet(artifacts[-1])
            logger.info(f"Session '{self.name}': Restored output_df from {artifacts[-1].name} ({len(self._output_df)} rows)")
