"""Narracao via Kokoro TTS (kokoro-82M, roda local, gratis, sem GPU).

Kokoro e um modelo aberto (Apache-2.0) de 82M de parametros: cabe em CPU
comum, sem CUDA. A propria documentacao (VOICES.md do hexgrad/Kokoro-82M)
avisa que suporte a lingua fora do ingles "pode ser fraco por G2P fraco e/ou
falta de dados de treino", e a tabela de vozes brasileiras nao tem nota de
qualidade nem duracao de treino, ao contrario das vozes em ingles.

O ponto que mais importa para este projeto: o Kokoro so devolve tempo de
cada palavra pronto (start_ts/end_ts) para lang_code em ingles ("a"/"b").
Para portugues (lang_code="p") ele devolve so a lista de fonemas por
palavra, sem nenhum tempo. Confirmado lendo o codigo (kokoro/pipeline.py,
join_timestamps so roda para MToken, que so existe no G2P em ingles).

O timing aqui embaixo e por isso ESTIMADO: a duracao total do audio e
dividida entre as palavras proporcional ao numero de fonemas de cada uma
(fonema aproxima melhor a duracao falada do que contar letra, porque nao e
enganado por letra muda nem digrafo). Ainda assim e estimativa, nao medicao.
O bug de audio corrigido nesta sessao veio exatamente de trocar estimativa
por medicao real do edge-tts: antes de usar isto ao vivo num canal com
legenda palavra por palavra, confirme a sincronia OLHANDO o video, nao so o
numero.
"""
import os
import re

import numpy as np
import soundfile as sf

from src.captions import _PUNCT

SAMPLE_RATE = 24000

# As tres vozes brasileiras do modelo (VOICES.md, secao Brazilian Portuguese).
VOICES = {
    "dora": "pf_dora",     # feminina
    "alex": "pm_alex",     # masculina
    "santa": "pm_santa",   # masculina
}

_pipeline_cache: dict = {}


def _pipeline():
    """Carrega o modelo uma vez so (leva ~20s) e reaproveita entre chamadas."""
    if "p" not in _pipeline_cache:
        import espeakng_loader
        # o pacote ja traz o binario do espeak-ng embutido, sem precisar
        # instalar nada a parte no Windows
        os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", espeakng_loader.get_library_path())
        from kokoro import KPipeline
        _pipeline_cache["p"] = KPipeline(lang_code="p")
    return _pipeline_cache["p"]


def _speed_from_rate(rate: str | None) -> float:
    """Converte a mesma notacao do config (tts_rate: "+8%") para o
    multiplicador de velocidade do Kokoro (1.08), para o campo valer para as
    duas vozes."""
    if not rate:
        return 1.0
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)%$", rate.strip())
    if not match:
        return 1.0
    return max(0.5, 1.0 + float(match.group(1)) / 100)


def synthesize_with_timings(text: str, voice: str, out_path: str,
                             rate: str | None = None) -> tuple[str, list[dict]]:
    """Mesma assinatura de src.tts.synthesize_with_timings, para caber no
    mesmo render_narration. Gera o audio (wav) e devolve o timing ESTIMADO de
    cada palavra (ver aviso no topo do arquivo)."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    speed = _speed_from_rate(rate)

    pedacos, fonemas_por_palavra = [], []
    for _, phonemes, audio in _pipeline()(text, voice=VOICES.get(voice, voice), speed=speed):
        pedacos.append(np.asarray(audio))
        fonemas_por_palavra.extend(phonemes.split())
    audio_total = np.concatenate(pedacos) if len(pedacos) > 1 else pedacos[0]
    sf.write(out_path, audio_total, SAMPLE_RATE)
    duracao = len(audio_total) / SAMPLE_RATE

    palavras = text.split()
    # o g2p as vezes agrupa token diferente do split() por espaco (ex.: numero
    # escrito por extenso vira mais de um token fonetico). Quando a contagem
    # nao bate, cai para peso igual por palavra em vez de desalinhar o resto.
    if len(fonemas_por_palavra) == len(palavras):
        pesos = [max(1, len(f)) for f in fonemas_por_palavra]
    else:
        pesos = [1] * len(palavras)
    total_peso = sum(pesos) or 1

    timings, cursor = [], 0.0
    for palavra, peso in zip(palavras, pesos):
        dur = duracao * peso / total_peso
        timings.append({"text": palavra.strip(_PUNCT), "start": cursor, "end": cursor + dur})
        cursor += dur
    return out_path, timings
