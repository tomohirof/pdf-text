import requests
import os

# APIエンドポイント
url = "http://localhost:5000/extract"

# テスト用PDFファイル
pdf_file = "pdf/【新卒】業績推移(コグナビ新卒)_202507 (1).pdf"

# ファイルが存在するか確認
if not os.path.exists(pdf_file):
    print(f"エラー: {pdf_file} が見つかりません")
    exit(1)

# PDFファイルをアップロード
with open(pdf_file, 'rb') as f:
    files = {'file': f}
    response = requests.post(url, files=files)

# レスポンスを確認
if response.status_code == 200:
    # ZIPファイルを保存
    with open('test_result.zip', 'wb') as f:
        f.write(response.content)
    print("成功！test_result.zip として保存されました")
else:
    print(f"エラー: {response.status_code}")
    print(response.json())