# PDF データ抽出ツール

PDFファイルから表データとテキストを抽出するWebアプリケーションです。

![PDF Extractor](https://img.shields.io/badge/PDF-Extractor-purple)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-green)

## 機能

- 📄 PDFからのテキスト抽出
- 📊 表データの自動検出と抽出
- 📁 Excel、CSV、テキスト形式での出力
- 🎯 ドラッグ&ドロップ対応
- 📦 結果をZIPファイルでダウンロード
- 🚀 Docker/CapRover対応

## 必要な環境

- Python 3.11+
- Java Runtime Environment (JRE)
- Docker (オプション)

## セットアップ

### ローカル環境

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# アプリケーションの起動
python app.py
```

### Docker環境

```bash
# コンテナのビルドと起動
docker-compose up --build

# ブラウザでアクセス
# http://localhost:5001/
```

## 使い方

1. ブラウザで `http://localhost:5001/` にアクセス
2. PDFファイルをドラッグ&ドロップまたは選択
3. 「処理を開始」ボタンをクリック
4. 処理完了後、ZIPファイルが自動的にダウンロード

## 出力形式

- **Excel形式**: すべてのデータを1つのファイルに複数シートで保存
- **CSV形式**: 各表を個別のファイルとして保存
- **テキスト形式**: PDFの全テキストを1つのファイルに保存

## 技術スタック

- **バックエンド**: Flask (Python)
- **PDF処理**: PyPDF2 (テキスト)、tabula-py (表)
- **データ処理**: pandas
- **フロントエンド**: HTML5, CSS3, JavaScript
- **コンテナ**: Docker

## テスト

```bash
# テストの実行
python -m pytest test_app.py -v
```

## デプロイ (CapRover)

1. GitリポジトリをCapRoverに接続
2. アプリケーション名を設定
3. デプロイを実行

## ライセンス

このプロジェクトはプライベート利用を目的としています。