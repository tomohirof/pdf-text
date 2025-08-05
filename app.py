import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from flask import Flask, request, send_file, jsonify, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
import tabula
import pandas as pd
from PyPDF2 import PdfReader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_EXTENSIONS'] = ['.pdf']
app.config['SECRET_KEY'] = 'your-secret-key-here'  # For flash messages

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PyPDF2"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        
        for page_num, page in enumerate(reader.pages):
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.extract_text()
        
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

def extract_tables_from_pdf(pdf_path):
    """Extract tables from PDF using tabula-py"""
    try:
        dfs = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        return dfs
    except Exception as e:
        print(f"Error extracting tables from PDF: {e}")
        return None

def process_table_with_newlines(df):
    """Process table to handle cells with newline-separated data"""
    processed_rows = []
    
    for _, row in df.iterrows():
        has_newline = any(isinstance(val, str) and '\r' in val for val in row)
        
        if has_newline:
            max_splits = max([len(str(val).split('\r')) if isinstance(val, str) and '\r' in val else 1 for val in row])
            
            for i in range(max_splits):
                new_row = []
                for val in row:
                    if isinstance(val, str) and '\r' in val:
                        split_vals = val.split('\r')
                        new_row.append(split_vals[i] if i < len(split_vals) else '')
                    else:
                        new_row.append(val if i == 0 else '')
                processed_rows.append(new_row)
        else:
            processed_rows.append(row.tolist())
    
    processed_df = pd.DataFrame(processed_rows, columns=df.columns)
    return processed_df

def save_to_excel(tables, text, base_filename, output_dir):
    """Save extracted tables and text to Excel file"""
    excel_filename = os.path.join(output_dir, f"{base_filename}_extracted.xlsx")
    
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        for i, df in enumerate(tables):
            processed_df = process_table_with_newlines(df)
            sheet_name = f'Table_{i+1}'
            processed_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        if text:
            text_df = pd.DataFrame({'Text Content': [text]})
            text_df.to_excel(writer, sheet_name='Text_Content', index=False)
    
    return excel_filename

def save_to_csv(tables, text, base_filename, output_dir):
    """Save extracted tables to CSV files"""
    csv_files = []
    
    for i, df in enumerate(tables):
        processed_df = process_table_with_newlines(df)
        csv_filename = os.path.join(output_dir, f"{base_filename}_table_{i+1}.csv")
        processed_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        csv_files.append(csv_filename)
    
    if text:
        text_filename = os.path.join(output_dir, f"{base_filename}_text.txt")
        with open(text_filename, 'w', encoding='utf-8') as f:
            f.write(text)
        csv_files.append(text_filename)
    
    return csv_files

def create_zip(files, zip_path):
    """Create a ZIP file containing all the output files"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            if os.path.exists(file_path):
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)

@app.route('/', methods=['GET'])
def index():
    """Display the upload form"""
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_pdf():
    """Handle PDF upload and extraction"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Invalid file format. Only PDF files are allowed"}), 400
    
    try:
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            filename = secure_filename(file.filename)
            base_filename = os.path.splitext(filename)[0]
            pdf_path = os.path.join(temp_dir, filename)
            file.save(pdf_path)
            
            # Extract text and tables
            text = extract_text_from_pdf(pdf_path)
            tables = extract_tables_from_pdf(pdf_path)
            
            if not tables and not text:
                return jsonify({"error": "No content could be extracted from the PDF"}), 422
            
            output_files = []
            
            # Save to Excel
            if tables:
                excel_file = save_to_excel(tables, text or "", base_filename, temp_dir)
                output_files.append(excel_file)
                
                # Save to CSV
                csv_files = save_to_csv(tables, text or "", base_filename, temp_dir)
                output_files.extend(csv_files)
            elif text:
                # Save text only
                text_filename = os.path.join(temp_dir, f"{base_filename}_text.txt")
                with open(text_filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                output_files.append(text_filename)
            
            # Create ZIP file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"{base_filename}_extracted_{timestamp}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            create_zip(output_files, zip_path)
            
            # Send ZIP file
            return send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
            
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload from web form"""
    if 'file' not in request.files:
        flash('ファイルが選択されていません')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('ファイルが選択されていません')
        return redirect(url_for('index'))
    
    if not file.filename.lower().endswith('.pdf'):
        flash('PDFファイルのみアップロード可能です')
        return redirect(url_for('index'))
    
    try:
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            filename = secure_filename(file.filename)
            base_filename = os.path.splitext(filename)[0]
            pdf_path = os.path.join(temp_dir, filename)
            file.save(pdf_path)
            
            # Extract text and tables
            text = extract_text_from_pdf(pdf_path)
            tables = extract_tables_from_pdf(pdf_path)
            
            if not tables and not text:
                flash('PDFからデータを抽出できませんでした')
                return redirect(url_for('index'))
            
            output_files = []
            
            # Save to Excel
            if tables:
                excel_file = save_to_excel(tables, text or "", base_filename, temp_dir)
                output_files.append(excel_file)
                
                # Save to CSV
                csv_files = save_to_csv(tables, text or "", base_filename, temp_dir)
                output_files.extend(csv_files)
            elif text:
                # Save text only
                text_filename = os.path.join(temp_dir, f"{base_filename}_text.txt")
                with open(text_filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                output_files.append(text_filename)
            
            # Create ZIP file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"{base_filename}_extracted_{timestamp}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            create_zip(output_files, zip_path)
            
            # Send ZIP file
            return send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
            
    except Exception as e:
        flash(f'処理中にエラーが発生しました: {str(e)}')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)