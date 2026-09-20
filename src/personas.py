"""Descricao fixa das figuras biblicas nas imagens.

Sem isso o gerador desenha cada personagem de um jeito: Jesus loiro de olhos
azuis numa cena e mediterraneo na seguinte. Aqui cada nome tem UMA descricao,
fiel ao que se sabe do primeiro seculo (pele morena, cabelo e barba escuros,
roupa de linho sem tintura), e ela entra no texto da imagem sempre igual.

A descricao vai logo depois do nome, no comeco do texto: os modelos de imagem
so leem as primeiras ~77 palavras-token, e o que vem antes pesa mais."""
import re

# no maximo duas por cena: com tres a descricao empurra o resto do texto
# (cenario, luz, estilo) para fora do que o modelo le
MAX_POR_CENA = 2


def build(config_personas: list[dict] | None) -> list[tuple[re.Pattern, str]]:
    """Le a lista do config.yaml e devolve (regex do nome, descricao)."""
    built = []
    for persona in config_personas or []:
        names = [n for n in persona.get("nomes", []) if n]
        visual = (persona.get("visual") or "").strip()
        if not names or not visual:
            continue
        pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b",
                             re.IGNORECASE)
        built.append((pattern, visual))
    return built


def apply(visual: str, personas: list[tuple[re.Pattern, str]],
          limit: int = MAX_POR_CENA) -> str:
    """Troca a primeira aparicao de cada nome por "Nome, descricao"."""
    used = 0
    for pattern, description in personas:
        if used >= limit:
            break
        match = pattern.search(visual)
        if not match:
            continue
        # so a primeira aparicao: repetir a descricao estoura o texto
        visual = (visual[:match.end()] + f", {description}," + visual[match.end():])
        used += 1
    return visual
