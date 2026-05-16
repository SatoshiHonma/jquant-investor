# マルチステージビルドを採用し、軽量な本番環境イメージを作成
FROM python:3.11-slim as builder

WORKDIR /app

# 必要なパッケージ（コンパイル等に必要なもの）をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


FROM python:3.11-slim

WORKDIR /app

# tzdataの設定（日本時間）
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*

# アプリケーションのコードをコピー
COPY . .

# 実行コマンド（後ほど agent の loop などをエントリーポイントにする想定）
# CMD ["python", "src/agent/loop.py"]
CMD ["tail", "-f", "/dev/null"]
