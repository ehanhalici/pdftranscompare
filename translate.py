from typing import Tuple
import datetime
import pathlib
import importlib

from lazy_loader import LazyProxy

Llama = LazyProxy("llama_cpp", "Llama")

_model_instance = None
_messages_template = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "source_lang_code": "en",
                "target_lang_code": "tr",
                "text": "",
                "image": None
            }
        ]
    }
]


def _get_model():
    """
    Modeli sadece ilk çeviri istendiğinde (process_translation çağrıldığında)
    fiziksel olarak GPU/VRAM'e yükler. Sonraki çağrılarda yüklü modeli döndürür.
    """
    global _model_instance
    if _model_instance is None:
        print("[*] INFO: Llama modeli şu an VRAM'e yükleniyor...")
        model_path = str(pathlib.Path("~/llm-models/translategemma-4b-it.Q8_0.gguf").expanduser())
        
        _model_instance = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=4096,
            verbose=False
        )
    return _model_instance


def process_translation(text: str) -> Tuple[str, float]:
    """Metni çevirir ve geçen süreyi döndürür."""
    start_time = datetime.datetime.now()
    
    model = _get_model()

    _messages_template[0]['content'][0]['text'] = text

    response = model.create_chat_completion(
        messages=_messages_template,
        max_tokens=len(text) * 4,
        temperature=0.0
    )

    translation = response['choices'][0]['message']['content'].strip()
    
    diff_time = datetime.datetime.now() - start_time
    return translation, diff_time.total_seconds()
