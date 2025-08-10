# DocLift

**Smart PDF Data Extraction** - Clean tables and text from any PDF — in seconds.

![DocLift](https://img.shields.io/badge/DocLift-Smart%20PDF%20Extraction-purple)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-green)

## Features

- 📄 **Text Extraction** - Extract all text content from PDFs
- 📊 **Smart Table Detection** - Automatically detect and extract tables with hybrid mode
- 🔍 **Intelligent Mode Selection** - Automatically choose the best extraction method based on PDF structure
- 📁 **Multiple Output Formats** - Excel, CSV, and text formats
- 🎯 **Drag & Drop Interface** - Simple and intuitive file upload
- 📦 **Batch Download** - Get all results in a single ZIP file
- 🚀 **Production Ready** - Docker and CapRover deployment support
- 🔢 **Numeric Data Handling** - Properly converts text numbers to Excel numbers (no more green triangles!)
- 🈯 **Japanese Support** - Full support for Japanese text and number formats

## Requirements

- Python 3.11+
- Java Runtime Environment (JRE)
- Docker (オプション)

## Setup

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the application
python app.py
```

### Docker

```bash
# Build and run container
docker-compose up --build

# Access in browser
# http://localhost:5001/
```

## Usage

1. Open `http://localhost:5001/` in your browser
2. Drag & drop or select your PDF file
3. Click "Start Processing" button
4. Download the ZIP file with all extracted data

## Output Formats

- **Excel**: All data in a single file with multiple sheets
- **CSV**: Each table saved as a separate file
- **Text**: All text content in a single file

## Tech Stack

- **Backend**: Flask (Python) with Gunicorn
- **PDF Processing**: 
  - PyPDF2 (text extraction)
  - tabula-py (table extraction)
  - pdfplumber (line detection)
- **Data Processing**: pandas, numpy
- **Frontend**: HTML5, CSS3, JavaScript
- **Container**: Docker

## Testing

```bash
# Run tests
python -m pytest test_app.py -v
```

## Hybrid Extraction Mode

DocLift automatically selects the optimal table extraction mode based on your PDF structure:

- **Stream Mode**: Detects tables based on text spacing (best for tables without borders)
- **Lattice Mode**: Detects tables based on lines (best for tables with borders)

### How It Works

1. Detects vertical lines on each page
2. Extracts tables using both modes and calculates quality scores
3. Selects the result with the higher score

## Deployment (CapRover)

1. Connect your Git repository to CapRover
2. Set up your application name
3. Deploy

## License

This project is for private use.