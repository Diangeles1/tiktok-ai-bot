"""Monta a linha de tempo das cenas: uma imagem e um trecho de narracao por
cena, com os tempos em segundos desde o inicio do video.

A narracao e sintetizada por cena (nao de uma vez), porque assim a duracao de
cada cena sai exata do proprio arquivo de audio. Cortar uma narracao unica nos
tempos das palavras erraria o ponto de troca de imagem."""
import os
import shutil
import subprocess

import numpy as np
from moviepy.editor import AudioFileClip

from src import personas as personas_mod, tts, tts_kokoro
from src.captions import attach_punctuation
from src.images import generate_scene_image


def render_images(scenes: list[dict], style: str, width: int, height: int,
                   out_dir: str, seed: int | None = None,
                   personas: list[dict] | None = None, melhor_mao: bool = True,
                   flux2: bool = True, continuidade: bool = True,
                   reserva_pollinations: bool = True) -> None:
    """Gera a imagem de cada cena e guarda o caminho em scene["image"].

    O mesmo sufixo de estilo vai em todas as cenas: sem isso cada imagem sai
    com uma pegada visual diferente e o video parece uma colagem. As figuras
    biblicas citadas ganham a descricao fixa do config (src/personas.py).
    flux2 usa o modelo que devolve o vertical inteiro em pintura; melhor_mao
    vale so no fallback, mandando a cena com gente para outro modelo (ver
    CLOUDFLARE_MODEL_FLUX2 e CLOUDFLARE_MODEL_PESSOA em src/images.py).

    continuidade manda a imagem da cena anterior como referencia da seguinte,
    para o video parecer o mesmo lugar filmado de outro angulo em vez de uma
    sequencia de quadros sem relacao (ver REF_MAX_SIDE em src/images.py). A
    descricao da cena continua mandando: quando a historia muda de lugar de
    verdade, o prompt vence a referencia, que ai carrega so luz e paleta."""
    os.makedirs(out_dir, exist_ok=True)
    built = personas_mod.build(personas)
    anterior = None
    for i, scene in enumerate(scenes):
        marca = "" if anterior is None else " (seguindo a cena anterior)"
        print(f"  [cena {i + 1}/{len(scenes)}]{marca} imagem: {scene['visual'][:60]}...")
        scene["image"] = generate_scene_image(
            prompt=f"{personas_mod.apply(scene['visual'], built)}, {style}",
            width=width,
            height=height,
            out_path=os.path.join(out_dir, f"scene_{i:02d}.jpg"),
            melhor_mao=melhor_mao,
            flux2=flux2,
            referencia=anterior if continuidade else None,
            reserva_pollinations=reserva_pollinations,
            # varia o seed por cena, senao todas as imagens saem parecidas
            seed=None if seed is None else seed + i,
        )
        anterior = scene["image"]


# o edge-tts entrega cada fala com silencio nas pontas (medido: ~0,16s no
# comeco e ~0,81s no fim). Somado ao respiro entre cenas, cada emenda virava
# 1,2s de silencio no meio da historia: a voz parava e voltava de uma vez, o
# que soa como defeito e derruba a retencao. Aparamos as pontas e deixamos so
# o respiro escolhido no config.
SILENCE_LEVEL = 0.01      # abaixo disso e silencio
# o edge-tts tambem para quase 1s depois de cada ponto (medido: 0,94 a 0,96s).
# No formato curto isso soa como se a voz tivesse cortado. Encurtamos para uma
# pausa de respiro e corrigimos o tempo das palavras junto, senao a legenda
# passa a adiantar em relacao a fala.
MAX_PAUSE = 0.34          # pausa interna maior que isso e encurtada
PAUSE_KEEP = 0.30         # tamanho que a pausa passa a ter
# A media por janela de 20ms pode classificar um trecho como silencio mesmo com
# uma respiracao ou consoante fraca escondida dentro dele. Cortar bem em cima
# disso soa como a voz sendo cortada (visto na pratica com o Kokoro, mais
# ruidoso que o edge-tts nos trechos quietos): antes de cortar, confere o pico
# so no pedaco que seria removido, nao a janela inteira.
PEAK_SAFETY = 1.3         # pico acima disto x SILENCE_LEVEL cancela o corte
CUT_FADE = 0.008          # fade de 8ms nas duas bordas de cada corte, contra clique
KEEP_HEAD = 0.05          # sobra no comeco, para a fala nao entrar cortada
KEEP_TAIL = 0.12          # sobra no fim, para a ultima silaba nao ser cortada
# fracao da energia da fala abaixo da qual o som no fim e cauda do modelo, e nao
# voz (ver _fim_da_fala). Medido: cauda ate 24%, silaba final fraca 57%.
TAIL_LEVEL_RATIO = 0.40
ANALYSIS_RATE = 16000


def _ffmpeg() -> str:
    achado = shutil.which("ffmpeg")
    if achado:
        return achado
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _pcm(path: str) -> np.ndarray:
    saida = subprocess.run([_ffmpeg(), "-v", "error", "-i", path, "-f", "s16le",
                            "-ac", "1", "-ar", str(ANALYSIS_RATE), "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(saida, dtype=np.int16).astype(np.float32) / 32768


def _fim_da_fala(amostras: np.ndarray) -> float:
    """Instante em que a fala de verdade acaba, ignorando a cauda do modelo.

    O Kokoro deixa depois da ultima silaba um rastro baixinho de 0,2 a 0,4s. Ele
    fica acima de SILENCE_LEVEL, entao a aparagem por silencio o preservava, e
    ele caia bem na pausa entre uma frase e a seguinte: e o "resquicio de voz"
    que aparecia no video.

    O limiar e relativo a energia da propria fala, e nao um valor fixo, porque
    cada voz e cada frase tem volume diferente. Medido nas 7 cenas de um video
    real: a cauda chega no maximo a 24% da energia da fala e a silaba final mais
    fraca vale 57%, entao 40% separa os dois com folga de 1,6x para cada lado.
    Essa folga e o que evita repetir o bug antigo de cortar a voz."""
    passo = max(1, int(0.02 * ANALYSIS_RATE))
    n = len(amostras) // passo
    if n == 0:
        return len(amostras) / ANALYSIS_RATE
    energia = np.sqrt((amostras[:n * passo].reshape(n, passo) ** 2).mean(axis=1))
    if energia.max() <= 0:
        return len(amostras) / ANALYSIS_RATE

    forte = energia[energia > energia.max() * 0.25]
    if not len(forte):
        return len(amostras) / ANALYSIS_RATE
    limiar = float(np.median(forte)) * TAIL_LEVEL_RATIO

    acima = np.where(energia >= limiar)[0]
    if not len(acima):
        return len(amostras) / ANALYSIS_RATE
    return (acima[-1] + 1) * 0.02


def trim_silence(path: str) -> tuple[str, float]:
    """Corta o silencio das pontas. Devolve o arquivo novo e quanto saiu do
    comeco, que e o quanto os tempos das palavras precisam andar para tras."""
    amostras = _pcm(path)
    acima = np.where(np.abs(amostras) > SILENCE_LEVEL)[0]
    if len(acima) == 0:
        return path, 0.0
    inicio = max(0.0, acima[0] / ANALYSIS_RATE - KEEP_HEAD)
    fim = min(len(amostras) / ANALYSIS_RATE, _fim_da_fala(amostras) + KEEP_TAIL)
    if fim - inicio < 0.2:
        return path, 0.0
    destino = os.path.splitext(path)[0] + "_apara.wav"
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-ss", f"{inicio:.3f}",
                    "-to", f"{fim:.3f}", "-i", path, "-ar", "44100", "-ac", "2",
                    "-c:a", "pcm_s16le", destino], check=True)
    return destino, inicio


def _silence_runs(samples: np.ndarray, rate: int) -> list[tuple[float, float]]:
    """Trechos de silencio (inicio, duracao) em segundos."""
    passo = max(1, int(0.02 * rate))
    n = len(samples) // passo
    if n == 0:
        return []
    energia = np.sqrt((samples[:n * passo].reshape(n, passo) ** 2).mean(axis=1))
    trechos, contando, inicio = [], 0, 0
    for i, e in enumerate(energia):
        if e < SILENCE_LEVEL:
            if contando == 0:
                inicio = i
            contando += 1
        else:
            if contando:
                trechos.append((inicio * 0.02, contando * 0.02))
            contando = 0
    if contando:
        trechos.append((inicio * 0.02, contando * 0.02))
    return trechos


def compress_pauses(path: str, timings: list[dict]) -> tuple[str, list[dict]]:
    """Encurta as pausas longas dentro da fala e move os tempos das palavras."""
    amostras = _pcm(path)
    cortes = []
    for inicio, duracao in _silence_runs(amostras, ANALYSIS_RATE):
        sobra = duracao - PAUSE_KEEP
        # so pausa interna: a do comeco e do fim ja foram aparadas
        if duracao <= MAX_PAUSE or sobra < 0.08 or inicio <= 0.05:
            continue
        if inicio + duracao >= len(amostras) / ANALYSIS_RATE - 0.05:
            continue
        corte_inicio = inicio + (duracao - sobra) / 2
        pedaco = amostras[int(corte_inicio * ANALYSIS_RATE):int((corte_inicio + sobra) * ANALYSIS_RATE)]
        if len(pedaco) and np.abs(pedaco).max() > SILENCE_LEVEL * PEAK_SAFETY:
            continue
        cortes.append((corte_inicio, sobra))
    if not cortes:
        return path, timings

    fim_total = len(amostras) / ANALYSIS_RATE
    pedacos, cursor = [], 0.0
    for corte_inicio, corte_duracao in cortes:
        pedacos.append((cursor, corte_inicio))
        cursor = corte_inicio + corte_duracao
    pedacos.append((cursor, fim_total))

    destino = os.path.splitext(path)[0] + "_ritmo.wav"
    filtro = ""
    for i, (a, b) in enumerate(pedacos):
        trecho = f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=N/SR"
        # fade nas bordas que colam em um corte: sem isso a emenda pode soar
        # como um clique, mesmo quando os dois lados sao mesmo silencio de verdade
        fade_d = min(CUT_FADE, (b - a) / 4)
        if i > 0:
            trecho += f",afade=t=in:st=0:d={fade_d:.4f}"
        if i < len(pedacos) - 1:
            trecho += f",afade=t=out:st={(b - a) - fade_d:.4f}:d={fade_d:.4f}"
        filtro += trecho + f"[p{i}];"
    filtro += "".join(f"[p{i}]" for i in range(len(pedacos)))
    filtro += f"concat=n={len(pedacos)}:v=0:a=1[out]"
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", path, "-filter_complex", filtro,
                    "-map", "[out]", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", destino],
                   check=True)

    def mover(t: float) -> float:
        saiu = 0.0
        for corte_inicio, corte_duracao in cortes:
            if t >= corte_inicio + corte_duracao:
                saiu += corte_duracao
            elif t > corte_inicio:
                saiu += t - corte_inicio
        return max(0.0, t - saiu)

    novos = [{"text": t["text"], "start": mover(t["start"]), "end": mover(t["end"])}
             for t in timings]
    return destino, novos


# Kokoro so escreve wav; o edge-tts escreve mp3. A extensao certa por
# provedor evita um arquivo com o container errado dentro do nome.
_PROVIDERS = {"edge": (tts, "mp3"), "kokoro": (tts_kokoro, "wav")}


def render_narration(scenes: list[dict], voice: str, out_dir: str, rate: str | None = None,
                      gap: float = 0.25, provider: str = "edge") -> float:
    """Sintetiza a narracao de cada cena e preenche scene["audio"], ["start"],
    ["duration"] e ["timings"] (tempos absolutos). Retorna a duracao total.

    provider="kokoro" usa o modelo local (ver src/tts_kokoro.py) em vez do
    edge-tts. ATENCAO: o timing de palavra do Kokoro em portugues e estimado,
    nao medido; confirme a sincronia da legenda olhando o video antes de usar
    ao vivo."""
    os.makedirs(out_dir, exist_ok=True)
    cursor = 0.0
    modulo, ext = _PROVIDERS[provider]

    for i, scene in enumerate(scenes):
        audio_path, timings = modulo.synthesize_with_timings(
            scene["narration"], voice, os.path.join(out_dir, f"scene_{i:02d}.{ext}"),
            rate=rate,
        )
        # o edge-tts devolve a palavra sem pontuacao; recuperada aqui, na
        # origem, para todo mundo que consome o timing ja receber certo
        timings = attach_punctuation(scene["narration"], timings)
        audio_path, cortado = trim_silence(audio_path)
        timings = [{"text": t["text"], "start": max(0.0, t["start"] - cortado),
                    "end": max(0.0, t["end"] - cortado)} for t in timings]
        audio_path, timings = compress_pauses(audio_path, timings)

        with AudioFileClip(audio_path) as clip:
            duration = clip.duration

        scene["audio"] = audio_path
        scene["start"] = cursor
        scene["duration"] = duration + gap
        scene["timings"] = [
            {"text": t["text"], "start": t["start"] + cursor, "end": t["end"] + cursor}
            for t in timings
        ]
        cursor += scene["duration"]

    return cursor


def all_timings(scenes: list[dict]) -> list[dict]:
    return [t for scene in scenes for t in scene["timings"]]
