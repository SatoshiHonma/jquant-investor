from pydantic import BaseModel, Field
from typing import List, Optional

class AnalysisCode(BaseModel):
    """
    Geminiが生成する分析コードの構造体
    """
    reasoning: str = Field(description="なぜこの分析コードを生成したのか、相場環境に基づいた意図")
    code: str = Field(description="AnalysisRunnerで実行可能なPythonコード（Pandas/NumPyを使用）")
    expected_outcome: str = Field(description="このコードを実行することで期待される出力内容（例：急騰銘柄のリスト）")

class StrategyResponse(BaseModel):
    """
    朝の戦略立案フェーズでのGeminiの回答形式
    """
    hypothesis: str = Field(description="今日の相場に関する仮説（マクロ環境などを考慮）")
    analysis_steps: List[AnalysisCode] = Field(description="仮説を検証するための分析ステップ（複数可）")

class EvaluationResponse(BaseModel):
    """
    大引け後の振り返りフェーズでのGeminiの回答形式
    """
    analysis: str = Field(description="前日の予想と実際の結果の乖離分析")
    lessons_learned: str = Field(description="失敗や成功から得られた教訓")
    prompt_adjustment: str = Field(description="翌日の戦略立案プロンプトへの改善指示")
