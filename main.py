from dataclasses import dataclass
from pathlib import Path

from helper import verify_pdf_path, verify_output_directory, generate_output_path, save_text_content
from pdf_to_html import pdf_to_html

def pipeline(pdf_path: str, output_directory: str, start_page: int, end_page: int):
    if start_page >= end_page:
        raise Exception("start_page can not be greater than end_page")

    pdf_path         = verify_pdf_path(pdf_path)
    output_directory = verify_output_directory(output_directory)
    output_path      = generate_output_path(pdf_path, output_directory)

    print("[] INFO Pdf Isleniyor")
    if not output_path.exists():
        html_content = pdf_to_html(str(pdf_path.resolve()))
        save_text_content(html_content, output_path)
        print(f"[] INFO Kaydedildi: {output_path}")
    else:
        print(f"[] INFO Pdf Zaten Var: {output_path}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python main.py <pdf_dosya_yolu> [çıktı_dosya_yolu] [start_page] [end_page]")
        sys.exit(1)

    pdf_path         = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) > 2 else "."
    start_page       = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    end_page         = int(sys.argv[4]) if len(sys.argv) > 4 else 9999999

    pipeline(pdf_path, output_directory, start_page, end_page)
