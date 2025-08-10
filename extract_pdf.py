import os
import tabula
import pandas as pd
import numpy as np
import pdfplumber
from PyPDF2 import PdfReader
from datetime import datetime
from typing import List, Optional, Tuple, Dict

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

def detect_vertical_lines(pdf_path: str, page_num: int, angle_tol_deg: float = 2.0) -> int:
    """Detect vertical lines in a PDF page using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num <= 0 or page_num > len(pdf.pages):
                return 0
            page = pdf.pages[page_num - 1]
            lines = page.lines or []
            count = 0
            for ln in lines:
                dx = abs(ln["x1"] - ln["x0"])
                dy = abs(ln["y1"] - ln["y0"])
                # Count vertical or nearly vertical lines
                if dy > 0 and dx / dy < np.tan(np.deg2rad(angle_tol_deg)):
                    count += 1
            return count
    except Exception as e:
        print(f"Error detecting vertical lines: {e}")
        return 0

def score_dataframe(df: pd.DataFrame) -> float:
    """Score extracted table quality (higher is better)"""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return -1.0
    
    # Basic metrics
    n_cols = df.shape[1]
    n_rows = df.shape[0]
    if n_cols <= 1:
        return -0.5
    
    # NaN ratio (lower is better)
    nan_ratio = df.isna().mean().mean()
    
    # Column quality metrics
    dup_cols_penalty = len(df.columns) - len(set(map(str, df.columns)))
    empty_cols = sum(df[col].astype(str).str.strip().eq("").mean() > 0.9 for col in df.columns)
    
    # Row count penalty for excessive rows (possible misextraction)
    size_penalty = 0.0
    if n_rows > 2000:
        size_penalty = 1.0
    
    # Calculate score
    score = (
        1.5 * np.log1p(n_rows) +
        2.0 * np.log1p(n_cols) -
        3.0 * nan_ratio -
        1.0 * dup_cols_penalty -
        1.0 * empty_cols -
        1.0 * size_penalty
    )
    return float(score)

def score_tables(dfs: List[pd.DataFrame]) -> float:
    """Calculate average score for multiple tables"""
    if not dfs:
        return -1.0
    return float(np.mean([score_dataframe(df) for df in dfs]))

def extract_tables_with_mode(pdf_path: str, pages: str = 'all', mode: str = 'stream', 
                           guess: bool = True) -> List[pd.DataFrame]:
    """Extract tables using specified mode (stream or lattice)"""
    try:
        kwargs = {'pages': pages, 'multiple_tables': True, 'guess': guess}
        if mode == 'stream':
            kwargs['stream'] = True
        elif mode == 'lattice':
            kwargs['lattice'] = True
        else:
            # Default behavior - let tabula decide
            pass
        
        dfs = tabula.read_pdf(pdf_path, **kwargs)
        return dfs or []
    except Exception as e:
        print(f"Error extracting tables with mode {mode}: {e}")
        return []

def extract_tables_hybrid(pdf_path: str, pages: str = 'all') -> Tuple[List[pd.DataFrame], Dict[int, str]]:
    """Extract tables using hybrid approach with automatic mode selection"""
    results = []
    mode_info = {}
    
    # Determine pages to process
    if pages == 'all':
        with pdfplumber.open(pdf_path) as pdf:
            page_numbers = list(range(1, len(pdf.pages) + 1))
    else:
        # For now, handle 'all' case. Can extend to parse page ranges later
        page_numbers = [1]  # Fallback to first page
    
    # Process each page
    for page_num in page_numbers:
        # Detect vertical lines
        vlines = detect_vertical_lines(pdf_path, page_num)
        initial_mode = 'lattice' if vlines >= 6 else 'stream'
        
        # Try both modes
        dfs_initial = extract_tables_with_mode(pdf_path, str(page_num), mode=initial_mode, guess=True)
        alt_mode = 'stream' if initial_mode == 'lattice' else 'lattice'
        dfs_alt = extract_tables_with_mode(pdf_path, str(page_num), mode=alt_mode, guess=True)
        
        # Score both results
        score_initial = score_tables(dfs_initial)
        score_alt = score_tables(dfs_alt)
        
        # Choose better result
        if score_alt > score_initial:
            results.extend(dfs_alt)
            mode_info[page_num] = alt_mode
        else:
            results.extend(dfs_initial)
            mode_info[page_num] = initial_mode
        
        # If both failed, try with guess=False
        if max(score_initial, score_alt) < 0:
            for mode in ['stream', 'lattice']:
                dfs_retry = extract_tables_with_mode(pdf_path, str(page_num), mode=mode, guess=False)
                if score_tables(dfs_retry) > max(score_initial, score_alt):
                    results = [df for df in results if df is not None]  # Remove previous results for this page
                    results.extend(dfs_retry)
                    mode_info[page_num] = mode
                    break
    
    return results, mode_info

def extract_tables_from_pdf(pdf_path, use_hybrid=True):
    """Extract tables from PDF using tabula-py with optional hybrid mode"""
    try:
        if use_hybrid:
            dfs, mode_info = extract_tables_hybrid(pdf_path)
            print(f"Hybrid extraction used modes: {mode_info}")
            return dfs
        else:
            # Classic mode - original behavior
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