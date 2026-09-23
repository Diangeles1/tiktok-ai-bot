"""Monta as legendas animadas (estilo CapCut) a partir do timing de palavras
retornado pelo edge-tts, e renderiza cada bloco como PNG transparente."""
import os

from PIL import Image, ImageDraw

from src.images import load_font

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
HIGHLIGHT = (255, 214, 10, 255)


# O edge-tts devolve a palavra nua: "dias." volta como "dias" e "Depois," como
# "Depois". A legenda montada so com esses timings sai sem pontuacao nenhuma, o
# que atrapalha a leitura e junta frases visualmente. A pontuacao e recuperada
# casando as palavras com o texto original da cena, que a tem.
_PUNCT = ".,;:!?()[]{}\"'"


def _core(token: str) -> str:
    return token.strip(_PUNCT).lower()


def attach_punctuation(narration: str, word_timings: list[dict]) -> list[dict]:
    """Devolve os timings com a pontuacao do texto original colada em cada palavra.

    Percorre as duas listas em paralelo. Quando a palavra do timing e o token do
    texto batem, o token (com pontuacao) substitui a palavra nua. Se nao baterem,
    o timing e mantido como veio: e melhor uma legenda sem virgula do que uma
    legenda deslocada em relacao a fala."""
    tokens = narration.split()
    ti = 0
    for token in tokens:
        if ti >= len(word_timings):
            break
        if _core(token) == _core(word_timings[ti]["text"]):
            word_timings[ti]["text"] = token.strip()
            ti += 1
    return word_timings


_FIM_DE_FRASE = (".", "!", "?", "...")


def _termina_frase(texto: str) -> bool:
    """A palavra fecha uma frase? Fecha-parenteses e aspas depois do ponto nao
    contam, por isso sao tirados antes de olhar o final."""
    return texto.rstrip(")]}\"'").endswith(_FIM_DE_FRASE)


def build_chunks(word_timings: list[dict], words_per_chunk: int = 3) -> list[dict]:
    """Agrupa palavras em blocos pequenos (ex: 3 em 3), guardando tambem as
    palavras do bloco para poder destacar a que esta sendo falada.

    O bloco nunca atravessa o fim de uma frase. Agrupando de N em N na marra, a
    legenda mostrava pedaco de duas frases ao mesmo tempo: num video real saiu
    "A 14. NO" na tela, juntando o fim de "...versiculos 8 a 14." com o comeco
    de "No campo...". Fora que da a impressao de erro, o espectador le um
    pedaco que nao quer dizer nada."""
    grupos: list[list[dict]] = []
    atual: list[dict] = []
    for palavra in word_timings:
        atual.append(palavra)
        if len(atual) >= words_per_chunk or _termina_frase(palavra["text"]):
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)

    # Frase de 4 palavras sairia como 3 + 1, e uma palavra sozinha na tela pisca
    # sem dar tempo de ler. Ela volta para o bloco anterior, desde que o anterior
    # seja da MESMA frase.
    ajustados: list[list[dict]] = []
    for grupo in grupos:
        if (len(grupo) == 1 and ajustados
                and len(ajustados[-1]) <= words_per_chunk
                and not _termina_frase(ajustados[-1][-1]["text"])):
            ajustados[-1].extend(grupo)
        else:
            ajustados.append(grupo)

    chunks = []
    for group in ajustados:
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
