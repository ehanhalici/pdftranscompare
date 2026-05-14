from dataclasses import dataclass

from pdf_extract import pdf_to_clean_html
from pdf_translate_and_merge import process_html_live



if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Kullanım: python pdf_extract.py <pdf_dosya_yolu> [çıktı_dosya_yolu] [start_page] [end_page]")
        sys.exit(1)

    pdf_path    = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "index.html"
    start_page  = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    end_page    = int(sys.argv[4]) if len(sys.argv) > 4 else 9999999

    html_result = pdf_to_clean_html(pdf_path, start_page, end_page)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_result)

    process_html_live(output_path)
