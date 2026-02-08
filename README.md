# PDF Semantic Converter

A Python-based application that converts PDFs to Semantic HTML while preserving high-fidelity layout using a hybrid rendering approach.

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Quick Start

1.  **Create a Virtual Environment (Recommended)**
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application**
    ```bash
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    
    The server works on `http://localhost:8000`.

## Features
- **High Fidelity**: SVG vector extraction and exact image placement.
- **Semantic HTML**: Extracts headings, paragraphs, and lists structure.
- **Hybrid Rendering**: Combines absolute positioning for layout with semantic markup for accessibility.

## Project Structure
- `app/`: Source code
  - `main.py`: FastAPI entry point
  - `parser.py`: PDF extraction logic (PyMuPDF)
  - `semantic.py`: AI/Heuristic semantic analysis
  - `renderer.py`: HTML generation
- `data/`: Data storage for uploads and results
