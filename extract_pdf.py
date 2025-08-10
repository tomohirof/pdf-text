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
    
    # Try to fix tables with potential column merge issues
    fixed_results = []
    for df in results:
        # Apply both fixing methods
        fixed_df = fix_merged_columns(df)
        # Apply advanced post-processing
        fixed_df = post_process_table(fixed_df)
        fixed_results.append(fixed_df)
    
    return fixed_results, mode_info

def fix_merged_columns(df):
    """Attempt to fix tables where multiple columns have been merged into one"""
    if df.empty:
        return df
    
    # Create a copy
    df_copy = df.copy()
    
    # Analyze all cells to detect consistent patterns of space-separated values
    max_parts_per_column = []
    split_info = []  # Store information about how to split each column
    
    for col_idx in range(len(df_copy.columns)):
        max_parts = 1
        # Analyze multiple rows to get a better understanding of the pattern
        value_patterns = []
        
        for _, row in df_copy.iterrows():
            cell_value = str(row.iloc[col_idx])
            if cell_value not in ['nan', 'NaN', '', None]:
                # Count space-separated parts
                parts = cell_value.split()
                if len(parts) > 1:
                    # Analyze each part
                    part_types = []
                    for p in parts:
                        clean_p = p.replace(',', '')
                        if clean_p.replace('.', '').replace('-', '').isdigit():
                            part_types.append('NUM')
                        elif '%' in p:
                            part_types.append('PCT')
                        elif any(c.isdigit() for c in p):
                            part_types.append('MIXED')
                        else:
                            part_types.append('TEXT')
                    
                    value_patterns.append((len(parts), part_types))
                    
                    # If most parts are numeric, consider splitting
                    numeric_count = sum(1 for t in part_types if t in ['NUM', 'PCT'])
                    if numeric_count >= len(parts) * 0.5:  # At least half are numeric
                        max_parts = max(max_parts, len(parts))
        
        max_parts_per_column.append(max_parts)
        split_info.append({'max_parts': max_parts, 'patterns': value_patterns})
    
    # If any column needs splitting, rebuild the dataframe
    if any(m > 1 for m in max_parts_per_column):
        new_data = []
        new_columns = []
        
        # Generate new column names based on the header and patterns
        for col_idx, (col_name, info) in enumerate(zip(df_copy.columns, split_info)):
            max_parts = info['max_parts']
            
            if max_parts > 1:
                col_str = str(col_name).strip()
                
                # Special handling for Japanese headers with specific patterns
                if '実績' in col_str and '見込' in col_str:
                    # This is likely a merged header like "実績+見込 実績 +見込 達成率※1"
                    header_parts = col_str.split()
                    if len(header_parts) >= max_parts:
                        new_columns.extend(header_parts[:max_parts])
                    else:
                        # Generate meaningful names based on pattern
                        new_columns.extend(header_parts)
                        for i in range(len(header_parts), max_parts):
                            new_columns.append(f"列{col_idx}_{i+1}")
                else:
                    # Try to split the header intelligently
                    header_parts = col_str.split()
                    if len(header_parts) == max_parts:
                        new_columns.extend(header_parts)
                    elif len(header_parts) > 1 and len(header_parts) < max_parts:
                        # Distribute header parts
                        new_columns.extend(header_parts)
                        for i in range(len(header_parts), max_parts):
                            new_columns.append(f"{col_name}_part{i+1}")
                    else:
                        # Generate numbered columns
                        for i in range(max_parts):
                            new_columns.append(f"{col_name}_col{i+1}")
            else:
                new_columns.append(col_name)
        
        # Process each row with improved splitting logic
        for _, row in df_copy.iterrows():
            new_row = []
            for col_idx, info in enumerate(split_info):
                max_parts = info['max_parts']
                cell_value = str(row.iloc[col_idx])
                
                if max_parts > 1:
                    if cell_value not in ['nan', 'NaN', '', None]:
                        parts = cell_value.split()
                        
                        # Ensure we have exactly max_parts values
                        if len(parts) >= max_parts:
                            new_row.extend(parts[:max_parts])
                        else:
                            # Intelligent padding based on the pattern
                            new_row.extend(parts)
                            # Fill remaining with empty strings
                            new_row.extend([''] * (max_parts - len(parts)))
                    else:
                        # Fill with empty strings for NaN values
                        new_row.extend([''] * max_parts)
                else:
                    new_row.append(cell_value if cell_value not in ['nan', 'NaN', None] else '')
            
            new_data.append(new_row)
        
        # Create new dataframe with split columns
        result_df = pd.DataFrame(new_data, columns=new_columns)
        
        # Clean up column names
        result_df.columns = [str(col).strip() for col in result_df.columns]
        
        # Remove any completely empty columns that might have been created
        result_df = result_df.loc[:, (result_df != '').any(axis=0)]
        
        return result_df
    
    return df_copy

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
    """Process table to handle cells with newline-separated data and space-separated values"""
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

def detect_column_structure(df):
    """Detect the structure of columns based on patterns in the data"""
    column_patterns = []
    
    for col_idx in range(len(df.columns)):
        patterns = []
        for _, row in df.iterrows():
            cell_value = str(row.iloc[col_idx])
            if cell_value not in ['nan', 'NaN', '', None]:
                # Analyze the pattern of the cell
                parts = cell_value.split()
                if parts:
                    # Record pattern: number of parts and their types
                    pattern = []
                    for part in parts:
                        # Remove commas and check if numeric
                        clean_part = part.replace(',', '').replace('.', '')
                        if clean_part.replace('-', '').isdigit():
                            pattern.append('NUM')
                        elif '%' in part:
                            pattern.append('PCT')
                        elif any(c.isdigit() for c in part):
                            pattern.append('MIXED')
                        else:
                            pattern.append('TEXT')
                    patterns.append(tuple(pattern))
        
        # Find the most common pattern for this column
        if patterns:
            from collections import Counter
            most_common_pattern = Counter(patterns).most_common(1)[0][0]
            column_patterns.append(most_common_pattern)
        else:
            column_patterns.append(())
    
    return column_patterns

def split_merged_cells_advanced(df):
    """Advanced splitting of merged cells based on detected patterns"""
    # First detect column patterns
    patterns = detect_column_structure(df)
    
    # Create new data structure
    new_data = []
    max_columns_needed = 0
    
    # First pass: determine maximum columns needed
    for col_idx, pattern in enumerate(patterns):
        if len(pattern) > 1:
            max_columns_needed += len(pattern)
        else:
            max_columns_needed += 1
    
    # Generate appropriate column headers
    new_columns = []
    col_counter = 0
    
    for col_idx, col_name in enumerate(df.columns):
        pattern = patterns[col_idx] if col_idx < len(patterns) else ()
        col_str = str(col_name).strip()
        
        if len(pattern) > 1:
            # Try to intelligently split the header
            header_parts = col_str.split()
            if len(header_parts) >= len(pattern):
                new_columns.extend(header_parts[:len(pattern)])
            else:
                # Use pattern to generate meaningful names
                for i, p in enumerate(pattern):
                    if i < len(header_parts):
                        new_columns.append(header_parts[i])
                    else:
                        suffix = ''
                        if p == 'NUM':
                            suffix = '数値'
                        elif p == 'PCT':
                            suffix = '率'
                        elif p == 'TEXT':
                            suffix = 'テキスト'
                        new_columns.append(f"列{col_counter+i+1}_{suffix}")
            col_counter += len(pattern)
        else:
            new_columns.append(col_name)
            col_counter += 1
    
    # Process each row
    for _, row in df.iterrows():
        new_row = []
        for col_idx, pattern in enumerate(patterns):
            cell_value = str(row.iloc[col_idx])
            
            if len(pattern) > 1 and cell_value not in ['nan', 'NaN', '', None]:
                parts = cell_value.split()
                # Ensure we match the pattern length
                if len(parts) >= len(pattern):
                    new_row.extend(parts[:len(pattern)])
                else:
                    new_row.extend(parts + [''] * (len(pattern) - len(parts)))
            elif len(pattern) > 1:
                # Fill with empty values for NaN cells
                new_row.extend([''] * len(pattern))
            else:
                new_row.append(cell_value if cell_value not in ['nan', 'NaN', None] else '')
        
        new_data.append(new_row)
    
    return pd.DataFrame(new_data, columns=new_columns)

def post_process_table(df):
    """Enhanced post-processing to handle complex table structures"""
    if df.empty:
        return df
    
    # First try the basic fix_merged_columns
    # This is already called in extract_tables_hybrid, but we'll ensure it's thorough
    processed_df = df.copy()
    
    # Additional cleanup and normalization
    # Replace various forms of NaN with empty strings
    processed_df = processed_df.replace(['nan', 'NaN', None, 'None'], '')
    
    # Try advanced splitting if needed
    if processed_df.shape[1] < 30:  # If we have fewer columns than expected
        processed_df = split_merged_cells_advanced(processed_df)
    
    # Final cleanup
    processed_df = processed_df.replace(['nan', 'NaN', None], '')
    
    # Remove completely empty rows and columns
    processed_df = processed_df.loc[(processed_df != '').any(axis=1)]
    processed_df = processed_df.loc[:, (processed_df != '').any(axis=0)]
    
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