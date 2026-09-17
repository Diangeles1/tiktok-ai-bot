"""Monta as legendas animadas (estilo CapCut) a partir do timing de palavras
retornado pelo edge-tts, e renderiza cada bloco como PNG transparente."""
import os

from PIL import Image, ImageDraw

from src.images import load_font


def build_chunks(word_timings: list[dict], words_per_chunk: int = 3) -> list[dict]:
    """Agrupa palavras em blocos pequenos (ex: 3 em 3) com o intervalo de tempo
    do primeiro ao ultimo timestamp do bloco."""
    chunks = []
    for i in range(0, len(word_timings), words_per_chunk):
        group = word_timings[i:i + words_per_chunk]
        chunks.append({
            "text": " ".join(w["text"] for w in group),
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })
    return chunks


def render_caption_png(text: str, width: int, out_path: str, font_size: int | None = None) -> tuple[str, int]:
    """Renderiza um bloco de legenda como PNG transparente. Retorna (path, altura_em_px)."""
    font_size = font_size or max(36, width // 14)
    font = load_font(font_size)

    height = int(font_size * 1.8)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), text.upper(), font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - text_w) / 2
    y = (height - text_h) / 2

    draw.text((x, y), text.upper(), font=font, fill=(255, 255, 255, 255),
               stroke_width=max(3, font_size // 12), stroke_fill=(0, 0, 0, 255))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    return out_path, height
