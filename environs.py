import os

envs = {
    "PYTORCH_CUDA_ALLOC_CONF" : (0, ["expandable_segments:True", "expandable_segments:False"]),
    
    # Doğru Surya batch size değişkenleri (SURYA_ ön eki yok)
    "DETECTOR_BATCH_SIZE"     : (0, ["1", "2", "3", "4"]),   # Bbox tespiti için (Hata aldığın asıl yer)
    "RECOGNITION_BATCH_SIZE"  : (0, ["1", "2", "3", "4"]),   # OCR okuması için
    "ORDER_BATCH_SIZE"        : (0, ["1", "2", "3", "4"]),   # Okuma sırası için
    
    "INFERENCE_RAM"           : (1, ["2", "4", "6", "8"]),   # Marker'ın bellek limiti
    "TORCH_DEVICE"            : (0, ["cuda", "cpu"]),
    "FIX_BROKEN_WORDS"        : (0, ["True", "False"])
}

def validate_env():
    for key, (value, probability) in envs.items():
        if os.environ.get(key) is None:
            os.environ[key] = probability[value]
        if os.environ.get(key, probability[value]) not in probability:
            raise Exception(f"[*] ERROR: os environ {key} is can be {probability}")
        print(f"[*] INFO: os environ {key}={os.environ[key]}, possible vals is : {probability}")
