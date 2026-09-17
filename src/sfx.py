"""Efeitos sonoros extras (ex: risada de grupo no final da esquete).

As risadas em assets/laughs/ vem do Mixkit (mixkit.co), licenca gratuita
sem exigencia de atribuicao para uso embutido em video."""
import glob
import random

LAUGHS_DIR = "assets/laughs"


def pick_random_laugh() -> str | None:
    """Retorna o caminho de uma risada aleatoria, ou None se nao houver nenhuma."""
    files = glob.glob(f"{LAUGHS_DIR}/*.mp3")
    return random.choice(files) if files else None
