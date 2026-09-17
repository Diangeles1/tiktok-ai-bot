"""Geracao de imagens via Pollinations.ai (gratuito, sem chave de API)
e composicao da legenda (burned-in caption) com Pillow."""
import os
import random
import textwrap
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFont

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


def generate_scene_image(prompt: str, width: int, height: int, out_path: str,
                          seed: int | None = None, retries: int = 4) -> str:
    """Baixa uma imagem gerada por IA para a cena. Retorna o caminho do arquivo.

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
            return out_path
        except requests.RequestException as exc:
            last_exc = exc
            wait = 5 * (attempt + 1)
            print(f"  [images] falha ao gerar imagem (tentativa {attempt + 1}/{retries}): {exc}. "
                  f"Tentando de novo em {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Nao foi possivel gerar a imagem apos {retries} tentativas: {last_exc}")


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def burn_caption(image_path: str, caption: str, out_path: str) -> str:
    """Sobrepoe o texto da cena na parte inferior da imagem (estilo legenda TikTok)."""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    font_size = max(28, img.width // 18)
    font = _load_font(font_size)

    wrapped = textwrap.fill(caption, width=22)
    lines = wrapped.split("\n")

    line_height = font_size + 10
    block_height = line_height * len(lines) + 60
    box_top = img.height - block_height - 140  # espaco para nao cobrir a UI do TikTok
    draw.rectangle([0, box_top, img.width, box_top + block_height], fill=(0, 0, 0, 140))

    y = box_top + 30
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (img.width - text_w) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                   stroke_width=2, stroke_fill=(0, 0, 0, 255))
        y += line_height

    img.save(out_path)
    return out_path
