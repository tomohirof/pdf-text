import pytest
import io
import zipfile
import os
from app import app

@pytest.fixture
def client():
    """Flaskテストクライアントのフィクスチャ"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def sample_pdf():
    """テスト用のPDFファイルのフィクスチャ"""
    # シンプルなPDFファイルのバイトデータを返す
    # 実際のテストでは最小限のPDFを使用
    return (io.BytesIO(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n203\n%%EOF'), 'test.pdf')

class TestWebInterface:
    """Webインターフェースのテスト"""
    
    def test_home_page_displays_upload_form(self, client):
        """ホームページにアップロードフォームが表示されることをテスト"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<form' in response.data
        assert b'type="file"' in response.data
        assert b'PDF' in response.data
    
    def test_upload_page_has_proper_elements(self, client):
        """アップロードページに必要な要素があることをテスト"""
        response = client.get('/')
        assert response.status_code == 200
        # フォームの action と method をチェック
        assert b'action="/upload"' in response.data or b'action="/extract"' in response.data
        assert b'method="POST"' in response.data or b'method="post"' in response.data
        assert b'enctype="multipart/form-data"' in response.data

class TestFileUpload:
    """ファイルアップロード機能のテスト"""
    
    def test_upload_pdf_returns_zip(self, client, sample_pdf):
        """PDFアップロードがZIPファイルを返すことをテスト"""
        data = {
            'file': sample_pdf
        }
        response = client.post('/upload', 
                             data=data,
                             content_type='multipart/form-data')
        
        # リダイレクトまたは直接ZIPを返す
        assert response.status_code in [200, 302]
        
        if response.status_code == 200:
            assert response.content_type == 'application/zip'
            # ZIPファイルとして読み込めることを確認
            zip_file = zipfile.ZipFile(io.BytesIO(response.data))
            assert len(zip_file.namelist()) > 0
    
    def test_upload_without_file(self, client):
        """ファイルなしでアップロードした場合のエラーテスト"""
        response = client.post('/upload', data={})
        assert response.status_code in [302, 400]  # リダイレクトまたはエラー
    
    def test_upload_non_pdf_file(self, client):
        """PDF以外のファイルをアップロードした場合のエラーテスト"""
        data = {
            'file': (io.BytesIO(b'Not a PDF'), 'test.txt')
        }
        response = client.post('/upload',
                             data=data,
                             content_type='multipart/form-data')
        assert response.status_code in [302, 400]  # リダイレクトまたはエラー

class TestProcessing:
    """PDF処理機能のテスト"""
    
    def test_process_pdf_with_text(self, client):
        """テキストを含むPDFの処理テスト"""
        # 実際のPDFファイルがある場合のテスト
        if os.path.exists('pdf/【新卒】業績推移(コグナビ新卒)_202507 (1).pdf'):
            with open('pdf/【新卒】業績推移(コグナビ新卒)_202507 (1).pdf', 'rb') as f:
                data = {'file': (f, 'test.pdf')}
                response = client.post('/upload',
                                     data=data,
                                     content_type='multipart/form-data')
                assert response.status_code in [200, 302]

class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    def test_large_file_rejected(self, client):
        """大きすぎるファイルが拒否されることをテスト"""
        # 16MB以上のダミーデータ
        large_data = b'0' * (17 * 1024 * 1024)
        data = {
            'file': (io.BytesIO(large_data), 'large.pdf')
        }
        response = client.post('/upload',
                             data=data,
                             content_type='multipart/form-data')
        # 413 Request Entity Too Large または他のエラー
        assert response.status_code in [413, 400, 302]
    
    def test_empty_filename(self, client):
        """ファイル名が空の場合のテスト"""
        data = {
            'file': (io.BytesIO(b'dummy'), '')
        }
        response = client.post('/upload',
                             data=data,
                             content_type='multipart/form-data')
        assert response.status_code in [400, 302]