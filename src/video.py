"""Montagem do video final: sequencia de cenas (imagem + narracao) com leve
zoom, legendas animadas palavra por palavra, risada e musica de fundo.

Um video de personagem fixo e so o caso de uma unica cena que dura a narracao
inteira, entao os dois formatos usam este mesmo caminho."""
import os
import statistics
import subprocess

import numpy as np
from moviepy.audio.fx.all import audio_fadein, audio_fadeout, audio_loop
from moviepy.editor import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                             ImageClip, VideoClip)
from PIL import Image, ImageDraw, ImageEnhance

from src.captions import BLACK, HIGHLIGHT, WHITE, build_chunks, render_chunk
from src.images import load_font
from src.thumbnail import _fit_text


def _ease(progress: float) -> float:
    """Smoothstep: acelera e desacelera nas pontas. Movimento linear entrega que
    e interpolacao de software; com easing parece movimento de camera."""
    return progress * progress * (3 - 2 * progress)


# Movimentos de camera alternados por cena, para o video nao ficar repetitivo:
# (zoom inicial, zoom final, pan inicial, pan final), pan em fracao do excedente
# da imagem (0 = borda esquerda/topo, 0.5 = centro, 1 = borda direita/base).
SUBSCRIBE_DURATION = 2.8  # tempo que o cartao de "se inscreva" fica na tela

CAMERA_MOVES = [
    (1.04, 1.16, (0.35, 0.50), (0.65, 0.50)),
    (1.16, 1.04, (0.65, 0.50), (0.35, 0.50)),
    (1.04, 1.16, (0.50, 0.62), (0.50, 0.38)),
    (1.16, 1.04, (0.50, 0.38), (0.50, 0.62)),
]

# Cada cena vira DOIS planos da mesma imagem, com um corte seco no meio: um
# aberto e depois um fechado em outro ponto do quadro. E o que editor de
# documentario faz com foto parada, e dobra o numero de cortes sem gerar uma
# imagem a mais. Sem isso a mesma imagem fica de 6 a 8 segundos na tela, quando
# o formato curto pede corte a cada 1,5 a 3 segundos.
# O plano fechado precisa ser mais fechado que o aberto para o olho ler corte e
# nao falha de video, mas sem exagero: a primeira versao ia ate 1.46 e ficou
# ruim de dois jeitos. Ampliava tanto que borrava (a janela vira 68% da imagem e
# e esticada de volta para 1080x1920), e principalmente cortava cabeca, porque a
# altura do enquadramento era escolhida as cegas: um alvo em 0.62 cai na roupa
# de quem esta em pe, nao no rosto. Ficou um anjo do pescoco para baixo.
# Agora o maximo e 1.34 e a ALTURA do plano fechado nao e mais fixa: vem de
# onde o assunto costuma estar naquele tipo de cena (_plano_fechado).
# Cada item: plano aberto completo, e do fechado so zoom e posicao horizontal.
SHOT_PAIRS = [
    ((1.02, 1.09, (0.50, 0.46), (0.52, 0.54)), (1.30, 1.24, 0.44, 0.52)),
    ((1.02, 1.06, (0.58, 0.50), (0.44, 0.50)), (1.26, 1.32, 0.56, 0.48)),
    ((1.02, 1.10, (0.42, 0.52), (0.56, 0.46)), (1.32, 1.26, 0.50, 0.44)),
    ((1.02, 1.08, (0.50, 0.56), (0.50, 0.44)), (1.28, 1.34, 0.46, 0.54)),
]
# Onde o plano fechado procura o assunto, em fracao da altura. Em cena com gente
# o rosto fica no terco superior do vertical (por isso 0.30, e nao o centro);
# em paisagem o interesse esta na linha do horizonte, perto do meio.
ALVO_VERTICAL_PESSOA = 0.30
ALVO_VERTICAL_PAISAGEM = 0.48
DERIVA_VERTICAL = 0.04    # quanto o enquadramento passeia em volta do alvo
# cena mais curta que isso nao se divide: dois planos de 2s cada atropelam a
# frase em vez de dar ritmo
SPLIT_MIN_SECONDS = 4.5


def _plano_fechado(spec: tuple, tem_pessoa: bool) -> tuple:
    """Monta o movimento do plano fechado mirando onde o assunto costuma estar."""
    zoom_de, zoom_para, x_de, x_para = spec
    alvo = ALVO_VERTICAL_PESSOA if tem_pessoa else ALVO_VERTICAL_PAISAGEM
    return (zoom_de, zoom_para,
            (x_de, alvo - DERIVA_VERTICAL), (x_para, alvo + DERIVA_VERTICAL))

# Acabamento de imagem, aplicado no encode final sobre o quadro inteiro (cena,
# legenda e marca d'agua juntas). Aplicar so na imagem deixaria a legenda com
# aparencia de adesivo colado por cima, em vez de parte da mesma cena.
#  - eq: contraste leve, que a imagem do gerador sai um pouco chapada
#  - colorbalance: luz quente no claro e sombra puxada para o azul, que e o
#    contraste de cor do "golden hour" que o cinema usa (a paleta do canal ja
#    pede ocre e azul, isso reforca)
#  - vignette: escurece o canto e puxa o olho para o centro, onde esta a acao.
#    PI/5 e mais suave que o PI/4.5 comum em video de terror
#  - noise: grao de filme. Alem do visual, ele quebra a "lisura" de imagem
#    gerada por IA, que e o que mais denuncia video automatico
ACABAMENTO = (
    "eq=contrast=1.06:saturation=1.03,"
    "colorbalance=rh=0.04:bh=-0.03:rs=-0.02:bs=0.05,"
    "vignette=PI/5,"
    "noise=alls=5:allf=t"
)


def _load_boosted(image_path: str, color_boost: float = 1.0) -> Image.Image:
    """Abre a imagem ja com o realce de cor aplicado.

    O gerador devolve imagem um pouco lavada e a correcao faz diferenca visivel
    no feed. Feito uma vez por cena, na abertura, e nao dentro do make_frame:
    aplicar por quadro multiplicaria o custo por 30 sem mudar o resultado."""
    source = Image.open(image_path).convert("RGB")
    if color_boost and abs(color_boost - 1.0) > 1e-3:
        source = ImageEnhance.Color(source).enhance(color_boost)
    return source


def _render_watermark(handle: str, width: int, out_path: str) -> tuple[str, int, int]:
    """Desenha o @ do canal em PNG transparente, com contorno para continuar
    legivel tanto sobre cena clara quanto escura."""
    font = load_font(max(18, int(width / 26)))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.textbbox((0, 0), handle, font=font, stroke_width=3)
    w, h = box[2] - box[0], box[3] - box[1]
    img = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((6 - box[0], 6 - box[1]), handle, font=font,
                              fill=(255, 255, 255, 255),
                              stroke_width=3, stroke_fill=(0, 0, 0, 255))
    img.save(out_path)
    return out_path, img.width, img.height


def _camera_move(image_path: str, duration: float, width: int, height: int, move: tuple,
                  color_boost: float = 1.0):
    """Ken Burns com easing: zoom e pan simultaneos sobre a imagem parada.

    Cada quadro e um recorte da imagem original redimensionado direto para o
    tamanho do video. Ampliar a imagem e reposicionar com offset seria o caminho
    obvio, mas ai qualquer erro de arredondamento no offset expoe faixa preta na
    beirada; recortando, o quadro sai sempre exato."""
    zoom_from, zoom_to, pan_from, pan_to = move
    source = _load_boosted(image_path, color_boost)
    src_w, src_h = source.size

    # maior janela com o aspecto do video que cabe na imagem, no zoom 1
    full_w = min(src_w, src_h * width / height)
    full_h = full_w * height / width

    def make_frame(t):
        progress = _ease(min(1.0, t / duration))
        zoom = zoom_from + (zoom_to - zoom_from) * progress
        win_w, win_h = full_w / zoom, full_h / zoom
        fx = pan_from[0] + (pan_to[0] - pan_from[0]) * progress
        fy = pan_from[1] + (pan_to[1] - pan_from[1]) * progress
        left = (src_w - win_w) * fx
        top = (src_h - win_h) * fy
        frame = source.resize((width, height), Image.BICUBIC,
                               box=(left, top, left + win_w, top + win_h))
        return np.asarray(frame)

    return VideoClip(make_frame, duration=duration)


_FOREGROUND_MASK_CACHE: dict = {}


def _foreground_mask(width: int, height: int) -> Image.Image:
    """Mascara em L (0 a 255): elipse solida onde o enquadramento 'medium shot'
    costuma por a pessoa (ver _tem_pessoa em src/images.py), com a borda
    esmaecendo ate transparente. E o que deixa o recorte do primeiro plano se
    fundir de volta no fundo sem mostrar uma costura retangular."""
    key = (width, height)
    if key not in _FOREGROUND_MASK_CACHE:
        y, x = np.ogrid[:height, :width]
        cx, cy = width / 2, height * 0.42
        rx, ry = width * 0.42, height * 0.32
        dist = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
        alpha = np.clip((1.2 - dist) / 0.6, 0.0, 1.0)
        _FOREGROUND_MASK_CACHE[key] = Image.fromarray((alpha * 255).astype("uint8"), mode="L")
    return _FOREGROUND_MASK_CACHE[key]


def _parallax_move(image_path: str, duration: float, width: int, height: int, move: tuple,
                    color_boost: float = 1.0):
    """Como _camera_move, mas com duas camadas na mesma imagem se movendo em
    velocidades diferentes: o "primeiro plano" (recorte central, onde a pessoa
    costuma estar) anda mais rapido que o fundo, fundido por uma mascara de
    borda suave (_foreground_mask). Sem modelo de profundidade nenhum: e a
    DIFERENCA de velocidade entre as duas que o olho le como profundidade real,
    nao so zoom sobre uma foto parada."""
    zoom_from, zoom_to, pan_from, pan_to = move
    source = _load_boosted(image_path, color_boost)
    src_w, src_h = source.size
    mask = _foreground_mask(width, height)

    full_w = min(src_w, src_h * width / height)
    full_h = full_w * height / width
    # >1: o primeiro plano percorre mais distancia que o fundo no mesmo tempo
    FG_FACTOR = 1.6

    def _window(fx, fy, zoom):
        win_w, win_h = full_w / zoom, full_h / zoom
        left = (src_w - win_w) * fx
        top = (src_h - win_h) * fy
        return left, top, left + win_w, top + win_h

    def make_frame(t):
        progress = _ease(min(1.0, t / duration))
        zoom = zoom_from + (zoom_to - zoom_from) * progress
        fx = pan_from[0] + (pan_to[0] - pan_from[0]) * progress
        fy = pan_from[1] + (pan_to[1] - pan_from[1]) * progress

        bg = source.resize((width, height), Image.BICUBIC, box=_window(fx, fy, zoom))
        fg_fx = 0.5 + (fx - 0.5) * FG_FACTOR
        fg_fy = 0.5 + (fy - 0.5) * FG_FACTOR
        fg = source.resize((width, height), Image.BICUBIC, box=_window(fg_fx, fg_fy, zoom))

        return np.asarray(Image.composite(fg, bg, mask))

    return VideoClip(make_frame, duration=duration)


def _render_subscribe_card(text: str, width: int, height: int, out_path: str) -> tuple[str, int]:
    """PNG transparente com o pedido de inscricao, mesma fonte/contorno da
    legenda animada. So entra quando assets/voz esta vazia (ver src/sfx.py
    pick_random_assinatura): a voz do dono e preferivel, isso e so um substituto
    ate voce gravar."""
    font, font_size, lines = _fit_text(text, width, max_lines=3, max_width_ratio=0.8,
                                        min_font_size=36)
    stroke = max(3, font_size // 11)
    line_h = int(font_size * 1.25)
    img_h = line_h * len(lines) + stroke * 2
    img = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        draw.text(((width - w) / 2, i * line_h), line, font=font,
                   fill=HIGHLIGHT if i == 0 else WHITE, stroke_width=stroke, stroke_fill=BLACK)
    img.save(out_path)
    return out_path, img_h


def _pop(clip, canvas_w: int, canvas_h: int, center_y: float,
          duration: float = 0.14, start_scale: float = 0.84):
    """Entrada da legenda: cresce rapido ate o tamanho normal. A posicao e
    recalculada junto com a escala para o centro do texto ficar parado, senao a
    legenda escorrega pela tela enquanto cresce."""
    def scale(t):
        if t >= duration:
            return 1.0
        return start_scale + (1 - start_scale) * _ease(t / duration)

    def position(t):
        current = scale(t)
        return (canvas_w * (1 - current) / 2, center_y - canvas_h * current / 2)

    return clip.resize(scale).set_position(position)


# ---------------------------------------------------------------------------
# NIVEL DA TRILHA: medido contra a VOZ, nao escolhido no escuro.
#
# Duas reclamacoes de "musica alta" foram atendidas baixando um numero absoluto
# (0.10 -> 0.06, depois um teto de 0.085) e a musica continuou alta. O numero
# absoluto nao podia resolver, por dois motivos medidos em 02/10/2026:
#
# 1. O que se ouve e a RELACAO com a voz, e a voz tambem e baixa. Medido:
#    narracao -26,1 dB RMS, trilha em 0.06 -> -39,4 dB RMS, ou seja a musica
#    ficava 13,3 dB abaixo da voz (10,3 dB no pico do crescimento). A
#    referencia de locucao sobre trilha e 15 a 20 dB abaixo.
# 2. As trilhas tem niveis MUITO diferentes entre si: the_journey mede -13,0 dB
#    RMS e a_new_life -20,7 dB, 7,7 dB de diferenca. Com ganho fixo, o volume
#    da musica dependia de qual trilha o clima sorteou.
#
# Entao o ganho passa a ser DERIVADO: mede-se a narracao, mede-se a trilha, e
# calcula-se o ganho que coloca a trilha N dB abaixo da voz. Isso corrige os
# dois de uma vez, e toda trilha nova entra no nivel certo sem ninguem ajustar
# nada.
#
# Por que 22 dB e nao 18: o dono do canal reclamou duas vezes, e feedback
# repetido do dono e evidencia. Errar para o lado silencioso e barato (a trilha
# e enfeite), errar para o lado alto atrapalha a narracao, que e o produto.
TRILHA_ABAIXO_DA_VOZ_DB = 22.0

# Os EFEITOS tinham o mesmo problema da trilha, e pior. Medido em 02/10/2026,
# com a narracao em -26,2 LUFS:
#
#   fanfarra (efeito de virada, volume 0.22) -> -25,6 LUFS: 0,6 dB MAIS ALTA
#   que a narracao. Ela dispara exatamente no inicio da ultima cena, e foi
#   isso que o dono do canal ouviu como "em 0:37 o audio estoura".
#   tensao_riser -> 2,1 dB abaixo da voz. impacto -> 2,9 dB abaixo.
#
# Os dez efeitos variam 25 dB entre si (passos -37,3 LUFS, fanfarra -12,5),
# entao volume fixo no cue nunca podia dar certo: o mesmo 0.22 produz coisas
# completamente diferentes. Agora cada efeito tambem e medido.
#
# Dois alvos, porque os dois papeis sao diferentes: a virada e um acento, tem
# que ser sentida sem cobrir a frase; o ambiente e textura e precisa ficar bem
# longe, porque vento e chuva sao ruido de banda larga, que e justamente o que
# mascara fala (e o que faz a voz parecer que esta chiando).
VIRADA_ABAIXO_DA_VOZ_DB = 18.0
AMBIENTE_ABAIXO_DA_VOZ_DB = 26.0

# Nivel de entrega do video inteiro. O mix saia a -25,4 LUFS, cerca de 11 dB
# abaixo dos -14 que as plataformas usam como alvo. Video baixo faz quem assiste
# subir o volume do aparelho, e alto-falante de celular no volume maximo
# distorce: e dai que vinha o "chiado". Normalizar aqui entrega o video no nivel
# que a plataforma espera, com folga de pico para o codec.
LOUDNESS_ALVO_LUFS = -16.0
# -2.0 e nao -1.0: alto-falante de celular distorce bem antes do fundo de
# escala, e o dono do canal relatou "estoura" com o pico medido em -1,4 dBFS.
# Meio decibel de folga nao muda a percepcao de volume e tira o risco.
PICO_VERDADEIRO_DBTP = -2.0

# Dinamica da trilha. O volume de base ja e baixo o
# bastante para nao disputar com a narracao: o que faltava era o outro lado, a
# trilha CRESCER. Ela sobe pouco antes da ultima cena, que e onde a historia
# vira, e volta ao normal enquanto a ultima fala acontece, para o crescimento
# nao atropelar justamente a frase mais importante.
# TETO ABSOLUTO da trilha, agora so como rede de seguranca. Ele nasceu porque o
# SWELL_PEAK desfazia a correcao de volume por tras do pano (0.06 x 2.2 = 0.132,
# mais alto que os 0.10 que ja tinham sido reclamados): duas constantes em
# arquivos diferentes e ninguem conferia o produto.
#
# Com o ganho DERIVADO da voz (ver TRILHA_ABAIXO_DA_VOZ_DB) o teto deixa de ser
# o controle principal, e um teto apertado passaria a atrapalhar: medido nas
# sete trilhas, o pico do crescimento com 22 dB de folga vai de 0.039
# (the_journey, a mais alta das fontes) a 0.094 (a_new_life, a mais baixa).
# Um teto de 0.085 cortaria justamente a trilha mais fraca e devolveria a
# diferenca entre trilhas que a medicao acabou de tirar. Entao o valor fica
# acima do maximo legitimo, servindo apenas para conter medicao absurda ou
# config errado.
TETO_DA_TRILHA = 0.12

SWELL_PEAK = 2.2      # multiplicador do volume de base no topo (cortado pelo teto)
SWELL_IN = 1.2        # tempo subindo, terminando no comeco da ultima cena
SWELL_HOLD = 0.4      # tempo no topo
SWELL_OUT = 2.5       # tempo voltando ao volume de base


_LOUDNESS_CACHE: dict = {}


def _loudness_db(caminho: str) -> float | None:
    """Loudness integrada do arquivo (LUFS), pelo loudnorm do ffmpeg.

    O resultado fica em cache por caminho: uma cena com o mesmo ambiente de
    outra mediria o mesmo arquivo de novo, e cada medicao e um processo de
    ffmpeg que decodifica o audio inteiro. O arquivo nao muda durante uma
    execucao, entao medir uma vez basta.

    POR QUE NAO O RMS MEDIO: o RMS inclui o silencio das pausas, entao uma
    narracao mais pausada mede mais baixa sem a voz ter mudado. Medido em
    02/10/2026, nas narracoes de duas geracoes: o RMS medio variou 2,9 dB entre
    elas (-26,1 e -29,0) enquanto a loudness integrada variou 0,85 dB (-25,70 a
    -26,55 em seis arquivos). A loudness tem gate, ignora os trechos quietos, e
    e por isso que ela e a medida de "quao alto isso soa".

    Devolve None se nao der para medir, e quem chama cai no valor do config:
    video sem trilha e pior que video com a trilha no volume de antes.
    """
    if caminho in _LOUDNESS_CACHE:
        return _LOUDNESS_CACHE[caminho]

    try:
        saida = subprocess.run(
            ["ffmpeg", "-nostats", "-i", caminho, "-vn",
             "-af", "loudnorm=print_format=json", "-f", "null", "-"],
            capture_output=True, timeout=300,
        ).stderr.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return None

    medido = None
    for linha in saida.splitlines():
        if '"input_i"' in linha:
            bruto = linha.split(":")[1].strip().strip(',').strip('"')
            try:
                valor = float(bruto)
            except ValueError:
                break
            # arquivo mudo mede -inf e nao serve de referencia para nada
            medido = valor if valor > -70 else None
            break

    _LOUDNESS_CACHE[caminho] = medido
    return medido


def _loudness_da_voz(scenes: list[dict]) -> float | None:
    """A referencia de nivel do video: a loudness da narracao.

    Tudo o mais (trilha, efeito de virada, ambiente) e posicionado em relacao a
    ela, porque e ela o produto: musica e efeito existem para servir a fala.

    Usa a MEDIANA de algumas cenas em vez de uma so: uma cena curta ou com mais
    pausa nao deve decidir o nivel do video inteiro.
    """
    medidas = [m for m in (_loudness_db(s["audio"])
                           for s in scenes[:3] if s.get("audio"))
               if m is not None]
    return statistics.median(medidas) if medidas else None


def _ganho_abaixo_da_voz(caminho: str, voz: float | None, abaixo_db: float,
                          fallback: float, rotulo: str,
                          teto: float = 1.0) -> float:
    """Ganho que coloca este arquivo `abaixo_db` dB abaixo da narracao.

    Mede os dois lados em vez de confiar em constante, porque os dois variam: a
    narracao depende da voz do TTS, cada trilha vem com o seu nivel de
    masterizacao (7,7 dB entre a mais alta e a mais baixa das sete do canal) e
    os efeitos variam 25 dB entre si (passos -37,3 LUFS, fanfarra -12,5). Com
    ganho fixo, o volume dependia de qual arquivo o roteiro sorteou.

    Falhando a medicao, devolve o valor de antes: video com o audio de antes e
    melhor que video sem trilha ou sem efeito.

    O `teto` e rede de seguranca contra medicao absurda, e por isso e diferente
    para cada uso: a trilha tem o seu (TETO_DA_TRILHA), e o efeito aceita ate
    ganho 1.0, porque um efeito gravado baixo (passos mede -37,3 LUFS) precisa
    LEGITIMAMENTE de ganho alto para chegar ao alvo. Usar o teto da trilha para
    tudo prendia justamente os efeitos mais quietos no lugar errado.
    """
    nivel = _loudness_db(caminho)
    if nivel is None or voz is None:
        print(f"  {rotulo}: nao consegui medir, usando o volume fixo ({fallback})")
        return fallback

    ganho = min(10 ** ((voz - abaixo_db - nivel) / 20), teto)
    print(f"  {rotulo}: voz {voz:.1f} LUFS, fonte {nivel:.1f} LUFS, "
          f"ganho {ganho:.4f} ({abaixo_db:.0f} dB abaixo da voz)")
    return ganho


def _ganho_trilha(t, virada: float | None, narration_end: float, total: float,
                  volume_base: float = 0.06):
    """Multiplicador do volume da trilha em cada instante.

    Aceita t escalar ou vetor de amostras, que e como o MoviePy chama."""
    tempo = np.asarray(t, dtype=float)
    ganho = np.ones_like(tempo)

    if virada is not None:
        # o pico efetivo nao passa do teto, seja qual for o volume de base
        pico = min(SWELL_PEAK, TETO_DA_TRILHA / max(volume_base, 1e-6))
        subida = np.clip((tempo - (virada - SWELL_IN)) / SWELL_IN, 0.0, 1.0)
        descida = 1.0 - np.clip((tempo - (virada + SWELL_HOLD)) / SWELL_OUT, 0.0, 1.0)
        ganho = ganho + (max(1.0, pico) - 1.0) * np.minimum(subida, descida)

    # sem a narracao por cima, o mesmo volume que era "de fundo" passa a soar
    # alto sozinho (feedback real: "a musica no final ficou muito alta"), entao
    # a partir do fim da narracao ela vai sumindo ate o corte
    if total > narration_end:
        saida = np.clip((tempo - narration_end) / (total - narration_end), 0.0, 1.0)
        ganho = ganho * (1.0 - saida)
    return ganho


def _com_dinamica(music, virada: float | None, narration_end: float, total: float,
                  volume_base: float = 0.06):
    def aplica(get_frame, t):
        quadro = get_frame(t)
        ganho = _ganho_trilha(t, virada, narration_end, total, volume_base)
        if np.ndim(quadro) == 2:          # bloco de amostras: (n, canais)
            return quadro * np.asarray(ganho).reshape(-1, 1)
        return quadro * ganho             # amostra unica
    return music.fl(aplica, keep_duration=True)


def _build_audio(scenes: list[dict], narration_end: float, total: float,
                  laugh_path: str | None, laugh_gap: float,
                  music_path: str | None, music_volume: float,
                  assinatura_path: str | None = None,
                  assinatura_gap: float = 0.45,
                  extra_sfx: list[dict] | None = None) -> tuple:
    tracks = [AudioFileClip(s["audio"]).set_start(s["start"]) for s in scenes]

    if laugh_path:
        tracks.append(AudioFileClip(laugh_path).set_start(narration_end + laugh_gap))

    if assinatura_path:
        tracks.append(AudioFileClip(assinatura_path).set_start(narration_end + assinatura_gap))

    # a narracao e a referencia de nivel de tudo o que vem por cima, e e medida
    # uma vez so: trilha e efeitos se posicionam em relacao a ela
    voz = _loudness_da_voz(scenes)

    if music_path:
        # o volume do config e o fallback: o valor usado sai da medicao
        music_volume = _ganho_abaixo_da_voz(music_path, voz,
                                             TRILHA_ABAIXO_DA_VOZ_DB,
                                             music_volume, "trilha",
                                             teto=TETO_DA_TRILHA)
        music = AudioFileClip(music_path).volumex(music_volume)
        music = audio_loop(music, duration=total)
        # a trilha deixa de ser um tapete de volume fixo e passa a ter dinamica:
        # cresce na virada da historia e some depois da narracao (ver _ganho_trilha)
        virada = scenes[-1]["start"] if len(scenes) > 2 else None
        music = _com_dinamica(music, virada, narration_end, total, music_volume)
        tracks.append(music)

    # efeitos de cena (vento, chuva, fanfarra...), bem baixos, para dar corpo
    # ao momento sem competir com a narracao. Cada item: path, start, papel e,
    # opcionalmente, duration (sem isso toca ate o fim do video: certo para um
    # efeito curto de virada, errado para um ambiente que deveria sumir com a
    # cena que o chamou) e volume, que hoje e so o fallback da medicao.
    #
    # O "papel" decide a distancia da voz: a virada e um acento e pode chegar
    # mais perto; o ambiente e textura e fica longe, porque vento e chuva sao
    # ruido de banda larga e e esse tipo de som que mascara a fala.
    for cue in (extra_sfx or []):
        abaixo = (VIRADA_ABAIXO_DA_VOZ_DB if cue.get("papel") == "virada"
                  else AMBIENTE_ABAIXO_DA_VOZ_DB)
        ganho = _ganho_abaixo_da_voz(cue["path"], voz, abaixo,
                                      cue.get("volume", 0.2),
                                      f"efeito {os.path.basename(cue['path'])}")
        efeito = AudioFileClip(cue["path"]).volumex(ganho)
        duracao_max = max(0.5, min(cue.get("duration", total), total - cue["start"]))
        if efeito.duration > duracao_max:
            efeito = efeito.subclip(0, duracao_max)
        efeito = audio_fadein(efeito, min(0.4, efeito.duration / 4))
        efeito = audio_fadeout(efeito, min(1.5, efeito.duration / 3)).set_start(cue["start"])
        tracks.append(efeito)

    mistura = CompositeAudioClip(tracks)
    # sem fps explicito o MoviePy escolhe pelo primeiro clipe, e um clipe com
    # taxa diferente (a trilha, por exemplo) sai reamostrado errado
    mistura.fps = max(getattr(t, "fps", 0) or 0 for t in tracks) or 44100
    return mistura, tracks


def _normalizar_loudness(caminho: str) -> bool:
    """Entrega o video no nivel que as plataformas usam como alvo.

    POR QUE: o mix saia a -25,4 LUFS, cerca de 11 dB abaixo do alvo. Video
    baixo faz quem assiste subir o volume do aparelho, e alto-falante de celular
    no volume maximo distorce. O "chiado" relatado nasce ai, e nenhuma mudanca
    de mixagem resolve, porque o problema e o nivel de ENTREGA.

    Duas passagens, que e como o loudnorm funciona de verdade: a primeira mede o
    arquivo inteiro, a segunda aplica com a medida na mao. Em uma passagem o
    filtro trabalha no escuro e o resultado fica longe do alvo.

    O VIDEO E COPIADO, nunca recomprimido ("-c:v copy"): so o audio e
    reescrito, entao a imagem sai identica. Se qualquer passo falhar, o arquivo
    original fica intacto e a publicacao segue com o audio de antes.
    """
    alvo = (f"I={LOUDNESS_ALVO_LUFS}:TP={PICO_VERDADEIRO_DBTP}:LRA=11")

    try:
        medida = subprocess.run(
            ["ffmpeg", "-nostats", "-i", caminho, "-vn",
             "-af", f"loudnorm={alvo}:print_format=json", "-f", "null", "-"],
            capture_output=True, timeout=600,
        ).stderr.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as erro:
        print(f"  AVISO: nao consegui medir o loudness ({erro}); audio sai como estava")
        return False

    campos = {}
    for chave in ("input_i", "input_tp", "input_lra", "input_thresh"):
        for linha in medida.splitlines():
            if f'"{chave}"' in linha:
                bruto = linha.split(":")[1].strip().strip(',').strip('"')
                try:
                    campos[chave] = float(bruto)
                except ValueError:
                    pass
                break
    if len(campos) < 4 or any(v == float("-inf") for v in campos.values()):
        print("  AVISO: medida de loudness incompleta; audio sai como estava")
        return False

    aplicado = (
        f"loudnorm={alvo}"
        f":measured_I={campos['input_i']}"
        f":measured_TP={campos['input_tp']}"
        f":measured_LRA={campos['input_lra']}"
        f":measured_thresh={campos['input_thresh']}"
    )
    temporario = caminho + ".loudnorm.mp4"
    try:
        feito = subprocess.run(
            ["ffmpeg", "-nostats", "-v", "error", "-y", "-i", caminho,
             "-c:v", "copy", "-af", aplicado,
             "-c:a", "aac", "-b:a", "192k", "-ar", "44100", temporario],
            capture_output=True, timeout=1800,
        )
    except (OSError, subprocess.SubprocessError) as erro:
        print(f"  AVISO: normalizacao falhou ({erro}); audio sai como estava")
        return False

    if feito.returncode != 0 or not os.path.exists(temporario):
        print("  AVISO: normalizacao falhou; audio sai como estava")
        if os.path.exists(temporario):
            os.remove(temporario)
        return False

    os.replace(temporario, caminho)
    print(f"  audio normalizado: {campos['input_i']:.1f} -> "
          f"{LOUDNESS_ALVO_LUFS:.0f} LUFS, pico em {PICO_VERDADEIRO_DBTP} dBTP")
    return True


def build_video(scenes: list[dict], width: int, height: int, fps: int, out_path: str,
                 words_per_chunk: int = 3, zoom_effect: bool = True, parallax_effect: bool = True,
                 tmp_dir: str = "output/_captions",
                 laugh_path: str | None = None, laugh_gap: float = 0.4,
                 assinatura_path: str | None = None, assinatura_gap: float = 0.45,
                 subscribe_text: str | None = None,
                 caption_bottom_margin: int = 420,
                 music_path: str | None = None, music_volume: float = 0.10,
                 extra_sfx: list[dict] | None = None,
                 crossfade: float = 0.6, tail: float = 1.2, color_boost: float = 1.0,
                 watermark: str | None = None, watermark_opacity: float = 0.35,
                 watermark_repeats: int = 4, acabamento: bool = True) -> str:
    """Cada cena precisa de "image", "audio", "start", "duration" e "timings"
    (tempos absolutos), como monta src.scenes."""
    narration_end = scenes[-1]["start"] + scenes[-1]["duration"]
    total = narration_end
    if laugh_path:
        with AudioFileClip(laugh_path) as laugh:
            total = narration_end + laugh_gap + laugh.duration
    if assinatura_path:
        # a voz do dono fecha o video: o tempo do video cresce para caber ela
        with AudioFileClip(assinatura_path) as assinatura:
            total = max(total, narration_end + assinatura_gap + assinatura.duration)
    elif subscribe_text:
        # sem gravacao de voz ainda, o pedido de inscricao vira um cartao de
        # texto no fim, no lugar da assinatura falada
        total = max(total, narration_end + assinatura_gap + SUBSCRIBE_DURATION)
    # respiro no fim: sem ele o corte cai junto com a ultima silaba e o video
    # parece interrompido
    total += tail

    # Dissolucao so na entrada da ULTIMA cena, que e onde a historia vira. Entre
    # as outras o corte e seco: em gramatica de cinema a dissolucao significa
    # "passou tempo", entao usar em toda emenda nao comunica nada e ainda
    # amolece cada corte, que e o que faz o video parecer apresentacao de
    # slides. Com menos de tres cenas nao ha virada para marcar.
    def _dissolucao_na_entrada(indice: int) -> float:
        return crossfade if (indice == len(scenes) - 1 and len(scenes) > 2) else 0.0

    scene_clips = []
    for i, scene in enumerate(scenes):
        is_last = i == len(scenes) - 1
        # a imagem passa do fim da propria cena so quando a proxima entra
        # dissolvendo, para ter algo por baixo; a ultima estica ate o fim para a
        # assinatura nao cair sobre tela preta
        sobra = 0.0 if is_last else _dissolucao_na_entrada(i + 1)
        visual_duration = (total - scene["start"]) if is_last else (scene["duration"] + sobra)
        entrada = _dissolucao_na_entrada(i)

        if not zoom_effect:
            frame = np.asarray(_load_boosted(scene["image"], color_boost))
            clip = (ImageClip(frame).set_duration(visual_duration)
                    .resize(height=height).set_position("center"))
            clip = clip.set_start(scene["start"])
            if entrada:
                clip = clip.crossfadein(entrada)
            scene_clips.append(clip)
            continue

        # so a cena com gente (medium shot, ver _tem_pessoa em src/images.py)
        # ganha o efeito de profundidade: tem um "primeiro plano" para
        # destacar. A cena aberta (wide shot, aerial view) e paisagem, sem
        # sujeito para separar, e fica no zoom de uma camada so.
        cena_com_gente = "medium shot" in scene.get("visual", "").lower()
        tem_pessoa = parallax_effect and cena_com_gente
        aberto, spec_fechado = SHOT_PAIRS[i % len(SHOT_PAIRS)]
        fechado = _plano_fechado(spec_fechado, cena_com_gente)

        if visual_duration >= SPLIT_MIN_SECONDS:
            # o plano aberto fica um pouco mais que o fechado: e nele que a
            # frase se estabelece, o fechado entra para acentuar
            dur_aberto = visual_duration * 0.55
            planos = [(aberto, 0.0, dur_aberto, tem_pessoa),
                      (fechado, dur_aberto, visual_duration - dur_aberto, False)]
        else:
            planos = [(aberto, 0.0, visual_duration, tem_pessoa)]

        for ordem, (move, offset, dur, usar_parallax) in enumerate(planos):
            if usar_parallax:
                clip = _parallax_move(scene["image"], dur, width, height, move, color_boost)
            else:
                clip = _camera_move(scene["image"], dur, width, height, move, color_boost)
            clip = clip.set_start(scene["start"] + offset)
            # so o primeiro plano da cena herda a dissolucao de entrada; o corte
            # entre os dois planos da MESMA cena e sempre seco
            if ordem == 0 and entrada:
                clip = clip.crossfadein(entrada)
            scene_clips.append(clip)

    caption_clips = []
    os.makedirs(tmp_dir, exist_ok=True)
    # Os blocos sao montados POR CENA. Achatar os timings de todas as cenas numa
    # lista so fazia um bloco de 3 palavras juntar o fim de uma cena com o inicio
    # da seguinte, atravessando o corte e a pausa entre elas: a legenda ficava
    # falando de uma cena por cima da imagem da outra.
    chunks = [(si, c) for si, scene in enumerate(scenes)
              for c in build_chunks(scene["timings"], words_per_chunk)]
    for i, (si, chunk) in enumerate(chunks):
        words = chunk["words"]
        paths, png_height = render_chunk([w["text"] for w in words], width,
                                          f"{tmp_dir}/cap_{si:02d}_{i:03d}")
        center_y = height - caption_bottom_margin - png_height / 2

        for j, path in enumerate(paths):
            # a palavra destacada troca quando a proxima comeca a ser falada; a
            # ultima do bloco segura ate o bloco acabar, para nao piscar na pausa
            start = words[j]["start"]
            end = words[j + 1]["start"] if j + 1 < len(words) else chunk["end"]
            clip = ImageClip(path).set_start(start).set_duration(max(0.05, end - start))
            if j == 0:
                clip = _pop(clip, width, png_height, center_y)
            else:
                clip = clip.set_position((0, center_y - png_height / 2))
            caption_clips.append(clip)

    # A marca d'agua aparece em varios pontos e troca de lugar. Repetir dificulta
    # que outro perfil baixe o video e corte a marca para repostar: tapar um
    # canto e facil, tapar quatro em posicoes diferentes estraga o video.
    watermark_clips = []
    if watermark and watermark_repeats > 0:
        wm_path, wm_w, wm_h = _render_watermark(watermark, width, f"{tmp_dir}/watermark.png")
        segment = total / watermark_repeats
        margin = width * 0.06
        for k in range(watermark_repeats):
            start = k * segment + segment * 0.15
            duration = min(4.0, segment * 0.55)
            if start + duration > total:
                break
            x = margin if k % 2 == 0 else width - wm_w - margin
            # mantida na metade de cima: embaixo ficaria por tras da legenda e
            # dentro da area que a interface do TikTok cobre
            y = height * (0.15 + 0.10 * (k % 3))
            watermark_clips.append(
                ImageClip(wm_path).set_start(start).set_duration(duration)
                .set_opacity(watermark_opacity).set_position((x, y))
                .crossfadein(0.4).crossfadeout(0.4)
            )

    subscribe_clips = []
    if subscribe_text and not assinatura_path:
        card_path, card_h = _render_subscribe_card(subscribe_text, width, height,
                                                     f"{tmp_dir}/subscribe.png")
        start = narration_end + assinatura_gap
        subscribe_clips.append(
            ImageClip(card_path).set_start(start).set_duration(total - start)
            .set_position(("center", (height - card_h) / 2))
            .crossfadein(0.4)
        )

    audio, audio_tracks = _build_audio(scenes, narration_end, total,
                                        laugh_path, laugh_gap, music_path, music_volume,
                                        assinatura_path, assinatura_gap, extra_sfx)

    final = CompositeVideoClip(scene_clips + caption_clips + watermark_clips + subscribe_clips,
                                size=(width, height))
    final = final.set_audio(audio).set_duration(total)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    final.write_videofile(
        out_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
        # o acabamento entra NO MESMO encode: aplicar depois exigiria
        # recomprimir o video inteiro de novo e perder qualidade
        ffmpeg_params=["-vf", ACABAMENTO] if acabamento else None,
    )

    final.close()
    for clip in scene_clips + caption_clips + watermark_clips + subscribe_clips + audio_tracks:
        clip.close()

    # O nivel de entrega e a ultima coisa a acertar, com o mix ja escrito: medir
    # antes seria medir um audio que ainda vai mudar. E vem DEPOIS de fechar os
    # clipes porque no Windows o os.replace falha enquanto alguem tem o arquivo
    # aberto, e o MoviePy so solta o handle no close.
    _normalizar_loudness(out_path)

    return out_path
