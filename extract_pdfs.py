#!/usr/bin/env python3
"""Extract text from PDF files for analysis."""

from pypdf import PdfReader
import sys

def extract_pdf_text(pdf_path):
    """Extract all text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

if __name__ == "__main__":
    pdf1 = "feelwell/2502.16051v2.pdf"
    pdf2 = "feelwell/nihms-2112836.pdf"
    
    print("=" * 80)
    print("PAPER 1: 2502.16051v2.pdf")
    print("=" * 80)
    text1 = extract_pdf_text(pdf1)
    print(text1)
    
    print("\n" + "=" * 80)
    print("PAPER 2: nihms-2112836.pdf")
    print("=" * 80)
    text2 = extract_pdf_text(pdf2)
    print(text2)
