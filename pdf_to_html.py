import os
import base64
from io import BytesIO

import torch
import markdown
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

def _configure_hardware_acceleration() -> str:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    os.environ["TORCH_DEVICE"] = device
    os.environ["INFERENCE_RAM"] = "16"
    print(device)
    return device

def _convert_pil_image_to_base64(pil_image_object) -> str:
    buffered_bytes = BytesIO()
    pil_image_object.save(buffered_bytes, format="JPEG")
    raw_bytes = buffered_bytes.getvalue()
    base64_encoded_string = base64.b64encode(raw_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{base64_encoded_string}"


def _embed_base64_images_into_html(html_content: str, image_dictionary: dict) -> str:
    modified_html = html_content
    for image_key, pil_image in image_dictionary.items():
        base64_uri = _convert_pil_image_to_base64(pil_image)
        modified_html = modified_html.replace(str(image_key), base64_uri)
    return modified_html


def _markdown_to_html(md_text: str) -> str:
    html_schema = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <style>
      body {{ font-family: sans-serif; max-width: 900px; margin: auto; padding: 20px; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
      img {{ max-width: 100%; height: auto; }}
      code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
      pre {{ background: #f4f4f4; padding: 12px; overflow-x: auto; border-radius: 6px; }}
      </style>
    </head>
    <body>
    {BODY}
    </body>
    </html>"""

    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "codehilite", "toc"],
    )
    return html_schema.format(BODY=body)

def _pdf_to_html(pdf_path: str, output_directory: str) -> str:
    execution_device = _configure_hardware_acceleration()

    machine_learning_models = create_model_dict(device=execution_device)
    document_converter = PdfConverter(artifact_dict=machine_learning_models)

    rendered = document_converter(pdf_path)

    markdown_content, _, extracted_images = text_from_rendered(rendered)

    raw_html_content = _markdown_to_html(markdown_content)

    return _embed_base64_images_into_html(raw_html_content, extracted_images)

