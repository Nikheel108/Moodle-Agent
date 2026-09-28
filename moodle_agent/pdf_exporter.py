"""Converts Markdown drafts to PDF format for submission."""

from __future__ import annotations

import logging
from pathlib import Path

import markdown
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

def convert_md_to_pdf(md_content: str, output_path: Path | str) -> tuple[bool, str]:
    """Converts markdown text to a PDF file.
    
    Args:
        md_content: The markdown string.
        output_path: Path where the PDF should be saved.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        # Convert Markdown to HTML
        html_content = markdown.markdown(
            md_content, 
            extensions=['tables', 'fenced_code', 'sane_lists']
        )
        
        # Wrap in basic HTML structure with CSS for better PDF rendering
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @page {{ size: a4 portrait; margin: 2cm; }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12pt; line-height: 1.5; color: #000000; }}
                h1 {{ color: #000000; border-bottom: 1px solid #000; padding-bottom: 5px; }}
                h2, h3, h4 {{ color: #000000; margin-top: 20px; }}
                pre {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace; font-size: 10pt; white-space: pre-wrap; color: #000000; }}
                code {{ background-color: #f8f9fa; padding: 2px 4px; font-family: monospace; border-radius: 3px; color: #000000; font-weight: normal; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; color: #000000; }}
                th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                strong, b {{ color: #000000; font-weight: bold; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        with open(output_path, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(
                src=full_html,
                dest=pdf_file
            )
            
        return (not pisa_status.err, '' if not pisa_status.err else 'PDF generation had internal errors')
        
    except Exception as e:
        logger.error(f"Failed to convert PDF: {e}")
        return (False, str(e))
