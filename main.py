import sys
from dataclasses import dataclass
from pathlib import Path

from helper import verify_pdf_path, verify_output_directory, generate_output_path, save_text_content
from pdf_to_html import pdf_to_html
from pdf_clean import strip_some_tag
from html_index_sentences import index_sentences_in_html
from pdf_translate_and_merge import pdf_translate_and_merge


def extract_pdf(pdf_path: Path, extract_path: Path) -> str:
    if extract_path.exists():
        print(f"[*] INFO Pdf Zaten Cikartilmis: {extract_path}")
        with open(str(extract_path)) as f:
            return f.read()
    else:
        html_content = pdf_to_html(str(pdf_path.resolve()))
        save_text_content(html_content, extract_path)
        print(f"[*] INFO Extract Kaydedildi: {extract_path}")
        return html_content

def clear_pdf(html_content: str, clear_path: Path) -> str:
    if clear_path.exists():
        print(f"[*] INFO Pdf Zaten Temizlenmis: {clear_path}")
        with open(str(clear_path)) as f:
            return f.read()
    else:
        html_content = strip_some_tag(html_content)
        save_text_content(html_content, clear_path)
        print(f"[*] INFO Clear Kaydedildi: {clear_path}")
        return html_content

def index_sentences(html_content: str, sentences_path: Path) -> str:
    if sentences_path.exists():
        print(f"[*] INFO Pdf Zaten cumlelere indexlenmis: {sentences_path}")
        with open(str(sentences_path)) as f:
            return f.read()
    else:
        html_content = index_sentences_in_html(html_content)
        save_text_content(html_content, sentences_path)
        print(f"[*] INFO Sentences Kaydedildi: {sentences_path}")
        return html_content
    
def pipeline(pdf_path: str, output_directory: str, start_page: int, end_page: int):
    if start_page >= end_page:
        raise Exception("start_page can not be greater than end_page")

    pdf_path         = verify_pdf_path(pdf_path)
    output_directory = verify_output_directory(output_directory)

    (extract_path,
     clear_path,
     sentences_path,
     translate_path) =  generate_output_path(pdf_path, output_directory)
    
    print("[*] INFO Pdf Isleniyor")

    html_content = extract_pdf(pdf_path, extract_path)
    html_content = clear_pdf(html_content, clear_path)
    html_content = index_sentences(html_content, sentences_path)
    pdf_translate_and_merge(html_content, translate_path)
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[*] Usage: python main.py <pdf_dosya_yolu> [çıktı_dosya_yolu] [start_page] [end_page]")
        sys.exit(1)

    pdf_path         = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) > 2 else "."
    start_page       = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    end_page         = int(sys.argv[4]) if len(sys.argv) > 4 else 9999999
    
    pipeline(pdf_path, output_directory, start_page, end_page)
