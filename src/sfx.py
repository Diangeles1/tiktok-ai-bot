"""Audio de apoio: risada de grupo no fim da esquete, musica de fundo e
efeitos sonoros de cena.

Os arquivos em assets/laughs/, assets/music/ e assets/sfx/ vem do Mixkit
(mixkit.co), licenca gratuita sem exigencia de atribuicao para uso embutido em
video (nem cadastro para baixar). Coloque arquivos novos seguindo a mesma
regra de licenca."""
import glob
import os
import random
import re

LAUGHS_DIR = "assets/laughs"
MUSIC_DIR = "assets/music"
SFX_DIR = "assets/sfx"
# gravacoes curtas do dono do canal fechando o video ("gostou? se inscreve no
# canal"). Varias, para o video nao terminar sempre igual.
ASSINATURA_DIR = "assets/voz"


def _pick_random(directory: str) -> str | None:
    files = glob.glob(f"{directory}/*.mp3")
    return random.choice(files) if files else None


def pick_random_laugh() -> str | None:
    """Retorna o caminho de uma risada aleatoria, ou None se nao houver nenhuma."""
    return _pick_random(LAUGHS_DIR)


def pick_music(clima: str | None = None) -> str | None:
    """Trilha aleatoria da pasta do clima pedido (ver src/script_gen.py
    CLIMAS), caindo para "calmo" se a pasta nao existir ou faltar musica.
    Sem clima, sorteia entre todas as pastas."""
    if clima:
        achada = _pick_random(f"{MUSIC_DIR}/{clima}")
        if achada:
            return achada
        achada = _pick_random(f"{MUSIC_DIR}/calmo")
        if achada:
            return achada
    files = glob.glob(f"{MUSIC_DIR}/*/*.mp3") or glob.glob(f"{MUSIC_DIR}/*.mp3")
    return random.choice(files) if files else None


# palavra do "visual" em ingles (ver src/script_gen.py) -> efeito sonoro que
# combina, tocado bem baixo por baixo DAQUELA cena para dar imersao (chuva
# quando chove, agua perto de um poco...) sem virar so uma trilha tensa o
# tempo todo. Ordem importa: primeiro achado vale, e a chuva ganha da tempestade
# generica porque e o efeito mais especifico das duas.
_AMBIENCE_KEYWORDS = (
    (re.compile(r"\brain\b", re.IGNORECASE), "chuva"),
    (re.compile(r"\b(thunder|lightning)\b", re.IGNORECASE), "trovao"),
    (re.compile(r"\b(river|water|well|sea|lake)\b", re.IGNORECASE), "agua"),
    (re.compile(r"\b(crowd|multitude|gathered|marketplace)\b", re.IGNORECASE), "multidao"),
    (re.compile(r"\b(desert|wilderness|wind|hillside|mountain)\b", re.IGNORECASE), "vento"),
    (re.compile(r"\b(night|dark|storm)\b", re.IGNORECASE), "vento_noturno"),
    (re.compile(r"\b(road|path|journey|walking)\b", re.IGNORECASE), "passos"),
)


def ambience_for_scene(visual: str) -> str | None:
    """Efeito de ambiente para UMA cena, pelo que o proprio prompt visual dela
    descreve (ver _AMBIENCE_KEYWORDS), ou None se nada bater. Chamado cena por
    cena: cada uma pode puxar um efeito diferente."""
    for padrao, nome in _AMBIENCE_KEYWORDS:
        if padrao.search(visual or ""):
            caminho = f"{SFX_DIR}/{nome}.mp3"
            if os.path.exists(caminho):
                return caminho
    return None


def resolution_cue(clima: str) -> str | None:
    """Efeito sonoro curto no comeco da ULTIMA cena, batendo com o clima da
    historia (ver src/script_gen.py CLIMAS). "calmo" nao ganha efeito: um
    estouro sonoro numa historia sem virada soaria fora de lugar."""
    nome = {"triunfante": "fanfarra", "tenso": "impacto"}.get(clima)
    if not nome:
        return None
    caminho = f"{SFX_DIR}/{nome}.mp3"
    return caminho if os.path.exists(caminho) else None


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
