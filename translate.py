from typing import Tuple
import datetime
import pathlib

from llama_cpp import Llama

class Translator:
    def __init__(self) -> None:
        model_path = str(pathlib.Path("~/llm-models/translategemma-4b-it.Q8_0.gguf").expanduser())
        
        self.model = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=4096,
            verbose=False
        )

        self.messages = [
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

    def process(self, text: str) -> Tuple[str, float]:
        #return text, 0.0
        #print(f"CEVRILIYOR \n{text}\n")
        start_time = datetime.datetime.now()
        
        self.messages[0]['content'][0]['text'] = text

        response = self.model.create_chat_completion(
            messages=self.messages,
            max_tokens=len(text) * 4,
            temperature=0.0
        )

        translation = response['choices'][0]['message']['content'].strip()
        #print(f"SONUC \n{translation}\n")
        diff_time = datetime.datetime.now() - start_time
        return translation, diff_time.total_seconds()
