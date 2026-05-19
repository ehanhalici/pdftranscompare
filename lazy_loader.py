import importlib

class LazyProxy:
    """Modülleri ve fonksiyonları sadece ilk kullanıldıklarında belleğe yükler."""
    def __init__(self, module_name, obj_name=None):
        self._module_name = module_name
        self._obj_name = obj_name
        self._obj = None

    def _load(self):
        if self._obj is None:
            # Modülü içe aktar
            module = importlib.import_module(self._module_name)
            # Eğer belirli bir fonksiyon/sınıf istenmişse onu al, yoksa tüm modülü al
            self._obj = getattr(module, self._obj_name) if self._obj_name else module
        return self._obj

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __call__(self, *args, **kwargs):
        return self._load()(*args, **kwargs)
