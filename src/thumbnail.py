"""Gera a capa do video: um quadro da cena com o texto de impacto por cima.

A capa sai no mesmo formato vertical do video, que e como o YouTube exibe
Shorts na prateleira do canal e na busca."""
import os

from PIL import Image, ImageDraw

from src.captions import BLACK, HIGHLIGHT, WHITE
from src.images import load_font


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """Recorta a imagem para cobrir exatamente o tamanho pedido, sem distorcer."""
    src_w, src_h = image.size
    target_aspect = width / height
    if src_w / src_h > target_aspect:
        win_h = src_h
        win_w = win_h * target_aspect
    else:
        win_w = src_w
        win_h = win_w / target_aspect
    left = (src_w - win_w) / 2
    top = (src_h - win_h) / 2
    return image.resize((width, height), Image.LANCZOS,
                         box=(left, top, left + win_w, top + win_h))


def _darken_bottom(image: Image.Image, ratio: float, strength: int) -> Image.Image:
    """Escurece a parte de baixo em degrade, senao o texto briga com a imagem."""
    width, height = image.size
    band_top = int(height * (1 - ratio))
    column = Image.new("L", (1, height), 0)
    for y in range(band_top, height):
        progress = (y - band_top) / max(1, height - 1 - band_top)
        column.putpixel((0, y), int(strength * progress))
    mask = column.resize((width, height))
    return Image.composite(Image.new("RGB", (width, height), (0, 0, 0)), image, mask)


def _wrap(draw: ImageDraw.ImageDraw, words: list[str], font, max_width: float) -> list[str]:
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(text: str, width: int, max_lines: int, max_width_ratio: float,
               min_font_size: int):
    """Maior fonte em que o texto cabe na largura dentro do limite de linhas."""
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    words = text.upper().split()
    max_width = width * max_width_ratio
    font_size = int(width / 6)

    while True:
        font = load_font(font_size)
        lines = _wrap(measure, words, font, max_width)
        widest = max(measure.textlength(line, font=font) for line in lines)
        if (len(lines) <= max_lines and widest <= max_width) or font_size <= min_font_size:
            return font, font_size, lines
        font_size -= 2


def build_thumbnail(scene_image: str, text: str, width: int, height: int, out_path: str,
                     max_lines: int = 3, max_words: int = 6, max_width_ratio: float = 0.88,
                     min_font_size: int = 40, darken_ratio: float = 0.55,
                     darken_strength: int = 215) -> str:
    """Monta a capa e retorna o caminho do arquivo.

    O texto e cortado em max_words: capa boa tem letra grande, e deixar o texto
    encolher para caber acaba em letra pequena que ninguem le na miniatura."""
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])

    with Image.open(scene_image) as source:
        base = _cover(source.convert("RGB"), width, height)
    base = _darken_bottom(base, darken_ratio, darken_strength)

    font, font_size, lines = _fit_text(text, width, max_lines, max_width_ratio, min_font_size)
    draw = ImageDraw.Draw(base)
    stroke = max(4, font_size // 11)
    line_height = int(font_size * 1.15)

    # texto ancorado acima da base, longe do selo de duracao do YouTube
    block_bottom = height - int(height * 0.13)
    y = block_bottom - line_height * len(lines)

    for index, line in enumerate(lines):
        line_width = draw.textlength(line, font=font)
        # a ultima linha sai na cor de destaque, a mesma das legendas do video
        color = HIGHLIGHT if index == len(lines) - 1 and len(lines) > 1 else WHITE
        draw.text(((width - line_width) / 2, y), line, font=font, fill=color,
                   stroke_width=stroke, stroke_fill=BLACK)
        y += line_height

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    base.save(out_path, quality=92)
    return out_path
