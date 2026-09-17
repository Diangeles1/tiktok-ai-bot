"""Monta as legendas animadas (estilo CapCut) a partir do timing de palavras
retornado pelo edge-tts, e renderiza cada bloco como PNG transparente."""
import os

from PIL import Image, ImageDraw

from src.images import load_font

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
HIGHLIGHT = (255, 214, 10, 255)


def build_chunks(word_timings: list[dict], words_per_chunk: int = 3) -> list[dict]:
    """Agrupa palavras em blocos pequenos (ex: 3 em 3), guardando tambem as
    palavras do bloco para poder destacar a que esta sendo falada."""
    chunks = []
    for i in range(0, len(word_timings), words_per_chunk):
        group = word_timings[i:i + words_per_chunk]
        chunks.append({
            "words": group,
            "text": " ".join(w["text"] for w in group),
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })

    # cada bloco dura ate o proximo comecar, senao a legenda pisca e some nas
    # pausas naturais da narracao
    for current, following in zip(chunks, chunks[1:]):
        current["end"] = following["start"]

    return chunks


def _fit_font(words: list[str], width: int, max_width_ratio: float,
               min_font_size: int) -> tuple:
    """Acha o maior tamanho de fonte em que o bloco inteiro cabe na largura."""
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    text = " ".join(words)
    font_size = max(36, width // 14)
    max_width = int(width * max_width_ratio)

    while True:
        font = load_font(font_size)
        stroke = max(3, font_size // 12)
        bbox = measure.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if (bbox[2] - bbox[0]) <= max_width or font_size <= min_font_size:
            return font, font_size, stroke, measure
        font_size -= 2


def render_chunk(words: list[str], width: int, out_prefix: str,
                  max_width_ratio: float = 0.9, min_font_size: int = 28) -> tuple[list[str], int]:
    """Renderiza um PNG por palavra destacada. Retorna (caminhos, altura do PNG).

    Os PNGs de um mesmo bloco compartilham o layout: as palavras ficam sempre na
    mesma posicao e so a cor muda, senao o texto tremeria a cada palavra."""
    words = [w.upper() for w in words]
    font, font_size, stroke, measure = _fit_font(words, width, max_width_ratio, min_font_size)

    space = measure.textlength(" ", font=font)
    widths = [measure.textlength(w, font=font) for w in words]
    total = sum(widths) + space * (len(words) - 1)

    height = int(font_size * 1.8)
    ascent, descent = font.getmetrics()
    baseline_y = (height - (ascent + descent)) / 2

    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    paths = []
    for active in range(len(words)):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        x = (width - total) / 2
        for i, word in enumerate(words):
            draw.text((x, baseline_y), word, font=font,
                       fill=HIGHLIGHT if i == active else WHITE,
                       stroke_width=stroke, stroke_fill=BLACK)
            x += widths[i] + space

        path = f"{out_prefix}_{active}.png"
        img.save(path)
        paths.append(path)

    return paths, height
