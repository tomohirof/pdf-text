# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PDF data extraction tool built with Python that extracts both text content and tabular data from PDF files and exports them to Excel, CSV, and text formats.

## Commands

### Setup and Development
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the extraction script
python extract_pdf.py
```

### Java Requirement
This project requires Java Runtime Environment (JRE) for tabula-py to function. If not installed:
```bash
# macOS with Homebrew
brew install openjdk
echo 'export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"' >> ~/.zshrc
```

## Architecture

### Core Components

1. **extract_pdf.py** - Main application containing:
   - `extract_text_from_pdf()`: Uses PyPDF2 to extract all text content
   - `extract_tables_from_pdf()`: Uses tabula-py to extract table data
   - `process_table_with_newlines()`: Handles cells containing newline-separated values by splitting them into separate rows
   - `save_to_excel()`: Exports all data to a single Excel file with multiple sheets
   - `save_to_csv()`: Exports each table to individual CSV files

### Data Flow
1. PDFs are placed in the `/pdf/` directory
2. Script processes all PDFs in batch
3. For each PDF:
   - Text is extracted using PyPDF2
   - Tables are extracted using tabula-py
   - Cells with newline characters (\r) are split into multiple rows
   - Data is saved with timestamps to prevent overwrites
4. Output files are saved to `/output/` directory

### Key Design Decisions
- **Newline Handling**: The tool specifically handles cells containing multiple values separated by `\r` characters, which is common in Japanese business documents
- **Timestamp Naming**: All output files include timestamps to prevent accidental overwrites during batch processing
- **Multiple Output Formats**: Provides flexibility by outputting to Excel (all data), CSV (individual tables), and text files