"""Geracao de imagens via Pollinations.ai (gratuito, sem chave de API)."""
import os
import random
import time
import urllib.parse

import requests
from PIL import Image, ImageFont

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

# A Pollinations grava a marca dela no rodape das imagens: o parametro
# nologo=true so vale para contas pagas. Cortamos a faixa porque o TikTok
# desqualifica da monetizacao conteudo com marca d'agua de outro app.
WATERMARK_STRIP_RATIO = 0.05


def generate_scene_image(prompt: str, width: int, height: int, out_path: str,
                          seed: int | None = None, retries: int = 4) -> str:
    """Baixa uma imagem gerada por IA. Retorna o caminho do arquivo.

    O servico gratuito da Pollinations.ai ocasionalmente responde 500/503 sob
    carga; como o bot roda sem supervisao, tentamos novamente com backoff."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    full_prompt = f"{prompt}, vertical composition, high detail, no text, no watermark"
    encoded = urllib.parse.quote(full_prompt)
    url = POLLINATIONS_URL.format(prompt=encoded)
    params = {
        "width": width,
        "height": height,
        "nologo": "true",
        "seed": seed if seed is not None else random.randint(1, 999_999),
    }

    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=120)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(resp.content)
            strip_watermark(out_path)
            return out_path
        except requests.RequestException as exc:
            last_exc = exc
            wait = 5 * (attempt + 1)
            print(f"  [images] falha ao gerar imagem (tentativa {attempt + 1}/{retries}): {exc}. "
                  f"Tentando de novo em {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Nao foi possivel gerar a imagem apos {retries} tentativas: {last_exc}")


def strip_watermark(path: str, ratio: float = WATERMARK_STRIP_RATIO) -> str:
    """Corta a faixa inferior da imagem, onde fica a marca d'agua da Pollinations."""
    with Image.open(path) as img:
        # a Pollinations responde JPEG: re-salvar como PNG multiplicaria o
        # tamanho de um arquivo que fica commitado no repo
        image_format = img.format
        width, height = img.size
        cropped = img.crop((0, 0, width, int(height * (1 - ratio))))

    options = {"quality": 95} if image_format == "JPEG" else {}
    cropped.save(path, format=image_format, **options)
    return path


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
