# Python 3.11とOpenJDKを含むベースイメージを使用
FROM python:3.11-slim

# システムパッケージの更新とJavaランタイム、curlのインストール
RUN apt-get update && apt-get install -y \
    default-jre \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 必要なディレクトリを作成
RUN mkdir -p /app/pdf /app/output

# 依存関係ファイルをコピー
COPY requirements.txt .

# Pythonパッケージのインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコピー
COPY extract_pdf.py .
COPY app.py .

# テンプレートディレクトリをコピー
COPY templates/ ./templates/

# 静的ファイルディレクトリをコピー
COPY static/ ./static/

# Java環境変数の設定（必要に応じて）
ENV JAVA_HOME=/usr/lib/jvm/default-java

# ポート80を公開
EXPOSE 80

# Gunicornを使用してFlaskアプリケーションを起動
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "4", "--timeout", "120", "app:app"]