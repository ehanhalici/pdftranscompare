import os
from pathlib import Path

def verify_pdf_path(pdf_path: str) -> Path:
    pdf_path = Path(pdf_path)
    if pdf_path.is_dir():
        raise Exception("pdf file path is not a file")
    if not pdf_path.exists():
        raise Exception("pdf file path is not exists")
    return pdf_path

def verify_output_directory(output_directory: str) -> Path:
    output_directory = Path(output_directory)
    if not output_directory.is_dir():
        raise Exception("output directory is not a directory")

    create_directory_if_missing(output_directory)
    return output_directory

def generate_output_path(input_path: Path, output_directory: Path) -> Path:
    document_name = get_filename_without_extension(input_path)
    output_html_path = os.path.join(output_directory, f"{document_name}.html")
    return Path(output_html_path)

def create_directory_if_missing(directory_path: Path) -> None:
    directory_path.mkdir(parents=True, exist_ok=True)


def save_text_content(content: str, file_path: Path) -> None:
    with open(file_path, "w", encoding="utf-8") as file_descriptor:
        file_descriptor.write(content)


def get_filename_without_extension(file_path: Path) -> str:
    return file_path.stem
