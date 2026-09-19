"""Audio de apoio: risada de grupo no fim da esquete e musica de fundo.

Os arquivos em assets/laughs/ vem do Mixkit (mixkit.co), licenca gratuita sem
exigencia de atribuicao para uso embutido em video. Coloque suas trilhas em
assets/music/ seguindo a mesma regra de licenca."""
import glob
import random

LAUGHS_DIR = "assets/laughs"
MUSIC_DIR = "assets/music"


def _pick_random(directory: str) -> str | None:
    files = glob.glob(f"{directory}/*.mp3")
    return random.choice(files) if files else None


def pick_random_laugh() -> str | None:
    """Retorna o caminho de uma risada aleatoria, ou None se nao houver nenhuma."""
    return _pick_random(LAUGHS_DIR)


def pick_random_music() -> str | None:
    """Retorna o caminho de uma trilha aleatoria, ou None se a pasta estiver vazia."""
    return _pick_random(MUSIC_DIR)
