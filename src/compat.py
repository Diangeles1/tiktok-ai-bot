"""Remendos de compatibilidade entre versoes das bibliotecas.

Importar este modulo ANTES de qualquer coisa que use MoviePy.

Pillow 10 removeu Image.ANTIALIAS, e o MoviePy 1.x ainda chama esse nome ao
redimensionar (video/fx/resize.py). Na maquina o MoviePy usa o OpenCV, que
esta instalado, e nada quebra; no GitHub Actions, sem OpenCV, ele cai no
Pillow e a montagem morre com AttributeError depois de gerar todas as imagens.
"""
from PIL import Image

for antigo, novo in (("ANTIALIAS", "LANCZOS"), ("BILINEAR", "BILINEAR"),
                     ("BICUBIC", "BICUBIC"), ("NEAREST", "NEAREST")):
    if not hasattr(Image, antigo):
        setattr(Image, antigo, getattr(Image.Resampling, novo))
