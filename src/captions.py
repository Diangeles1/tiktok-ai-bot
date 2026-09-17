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

    # cada bloco dura ate o proximo comecar, senao a legenda pisca e some nas
    # pausas naturais da narracao
    for current, following in zip(chunks, chunks[1:]):
        current["end"] = following["start"]

    return chunks


def render_caption_png(text: str, width: int, out_path: str, font_size: int | None = None,
                        max_width_ratio: float = 0.9, min_font_size: int = 28) -> tuple[str, int]:
    """Renderiza um bloco de legenda como PNG transparente. Retorna (path, altura_em_px).

    O tamanho da fonte e reduzido automaticamente se o bloco de palavras nao
    couber na largura do video (bloco com palavras longas), pra legenda nunca
    sair cortada nas bordas."""
    text = text.upper()
    font_size = font_size or max(36, width // 14)
    max_width = int(width * max_width_ratio)

    measure_img = Image.new("RGBA", (1, 1))
    measure_draw = ImageDraw.Draw(measure_img)

    while True:
        font = load_font(font_size)
        stroke_width = max(3, font_size // 12)
        bbox = measure_draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_w = bbox[2] - bbox[0]
        if text_w <= max_width or font_size <= min_font_size:
            break
        font_size -= 2

    text_h = bbox[3] - bbox[1]
    height = int(font_size * 1.8)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x = (width - text_w) / 2 - bbox[0]
    y = (height - text_h) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255),
               stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    return out_path, height
