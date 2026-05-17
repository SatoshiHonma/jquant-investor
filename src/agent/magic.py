"""
%%chat マジックコマンド: Sessionに委譲するだけの薄いUI層。
"""

import re
from IPython.core.magic import (Magics, magics_class, cell_magic)
from IPython import get_ipython
from IPython.display import display, Markdown
import pandas as pd


@magics_class
class JQuantsMagic(Magics):

    @cell_magic
    def chat(self, line, cell):
        """
        使い方:
            %%chat
            大陽線の銘柄を探して。

        セッションはNotebook上で `session` 変数として定義されている必要がある。
        """
        ip = get_ipython()
        session = ip.user_ns.get("session")

        if session is None:
            display(Markdown("⚠️ `session` が未定義です。先に `session = Session(...)` を実行してください。"))
            return

        display(Markdown(f"*(**{session.name}** が考え中...)*"))

        reply, exec_result = session.chat(cell)

        # AIの回答を表示
        display(Markdown(f"**🤖 {session.name}**:\n\n{reply}"))

        # コード実行結果があれば表示
        if exec_result is not None:
            display(Markdown("---"))
            if exec_result.get("success"):
                display(Markdown("✅ **実行完了**"))
                if exec_result.get("result"):
                    display(Markdown(f"> {exec_result['result']}"))
                if exec_result.get("output_df") is not None:
                    display(exec_result["output_df"])
            else:
                display(Markdown(f"❌ **実行エラー**\n\n```text\n{exec_result.get('error')}\n```"))


def load_ipython_extension(ipython):
    ipython.register_magics(JQuantsMagic)
