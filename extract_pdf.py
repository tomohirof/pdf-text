import os
import tabula
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime

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
        # Check if any cell in the row contains newline characters
        has_newline = any(isinstance(val, str) and '\r' in val for val in row)
        
        if has_newline:
            # Split cells with newlines and create multiple rows
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
    
    # Create new dataframe with processed rows
    processed_df = pd.DataFrame(processed_rows, columns=df.columns)
    return processed_df

def save_to_excel(tables, text, base_filename):
    """Save extracted tables and text to Excel file"""
    excel_filename = f"output/{base_filename}_extracted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        for i, df in enumerate(tables):
            # Process table to handle newlines
            processed_df = process_table_with_newlines(df)
            sheet_name = f'Table_{i+1}'
            processed_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        text_df = pd.DataFrame({'Text Content': [text]})
        text_df.to_excel(writer, sheet_name='Text_Content', index=False)
    
    print(f"Saved to Excel: {excel_filename}")
    return excel_filename

def save_to_csv(tables, text, base_filename):
    """Save extracted tables to CSV files"""
    csv_files = []
    
    for i, df in enumerate(tables):
        # Process table to handle newlines
        processed_df = process_table_with_newlines(df)
        csv_filename = f"output/{base_filename}_table_{i+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        processed_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        csv_files.append(csv_filename)
        print(f"Saved table {i+1} to CSV: {csv_filename}")
    
    text_filename = f"output/{base_filename}_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(text_filename, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Saved text to: {text_filename}")
    
    return csv_files

def main():
    pdf_dir = "pdf"
    output_dir = "output"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for filename in os.listdir(pdf_dir):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(pdf_dir, filename)
            base_filename = os.path.splitext(filename)[0]
            
            print(f"\nProcessing: {filename}")
            print("=" * 50)
            
            print("\n[Extracting text content...]")
            text = extract_text_from_pdf(pdf_path)
            if text:
                print(f"Extracted {len(text)} characters of text")
            
            print("\n[Extracting tables...]")
            tables = extract_tables_from_pdf(pdf_path)
            if tables:
                print(f"Found {len(tables)} table(s)")
                
                print("\n[Saving to Excel...]")
                save_to_excel(tables, text or "", base_filename)
                
                print("\n[Saving to CSV...]")
                save_to_csv(tables, text or "", base_filename)
            else:
                print("No tables found or error occurred")
                
                if text:
                    text_filename = f"output/{base_filename}_text_only_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(text_filename, 'w', encoding='utf-8') as f:
                        f.write(text)
                    print(f"Saved text only to: {text_filename}")

if __name__ == "__main__":
    main()