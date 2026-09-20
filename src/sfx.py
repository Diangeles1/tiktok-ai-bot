"""Audio de apoio: risada de grupo no fim da esquete e musica de fundo.

Os arquivos em assets/laughs/ vem do Mixkit (mixkit.co), licenca gratuita sem
exigencia de atribuicao para uso embutido em video. Coloque suas trilhas em
assets/music/ seguindo a mesma regra de licenca."""
import glob
import random

LAUGHS_DIR = "assets/laughs"
MUSIC_DIR = "assets/music"
# gravacoes curtas do dono do canal fechando o video ("gostou? se inscreve no
# canal"). Varias, para o video nao terminar sempre igual.
ASSINATURA_DIR = "assets/voz"


def _pick_random(directory: str) -> str | None:
    files = glob.glob(f"{directory}/*.mp3")
    return random.choice(files) if files else None


def pick_random_laugh() -> str | None:
    """Retorna o caminho de uma risada aleatoria, ou None se nao houver nenhuma."""
    return _pick_random(LAUGHS_DIR)


def pick_random_music() -> str | None:
    """Retorna o caminho de uma trilha aleatoria, ou None se a pasta estiver vazia."""
    return _pick_random(MUSIC_DIR)


def pick_random_assinatura() -> str | None:
    """Uma das gravacoes do dono do canal, ou None se a pasta estiver vazia.

    Aceita mp3 e m4a, que e o que sai da gravacao de celular."""
    for extensao in ("mp3", "m4a", "wav"):
        achados = _pick_random_ext(ASSINATURA_DIR, extensao)
        if achados:
            return achados
    return None


def _pick_random_ext(directory: str, extensao: str) -> str | None:
    files = glob.glob(f"{directory}/*.{extensao}")
    return random.choice(files) if files else None
