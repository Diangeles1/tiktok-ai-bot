"""Narracao via edge-tts (gratuito, sem chave de API)."""
import asyncio
import os

import edge_tts


async def _synthesize(text: str, voice: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def synthesize_scene_audio(text: str, voice: str, out_path: str) -> str:
    """Gera um arquivo mp3 com a narracao do texto. Retorna o caminho do arquivo."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    asyncio.run(_synthesize(text, voice, out_path))
    return out_path


async def _synthesize_with_timings(text: str, voice: str, out_path: str,
                                    rate: str | None = None) -> list[dict]:
    # edge-tts >=7 so envia timing por palavra se boundary="WordBoundary" for
    # pedido explicitamente (o padrao da lib mudou para "SentenceBoundary").
    # rate acelera a leitura. A voz padrao fica arrastada para formato curto, e
    # o edge-tts reajusta os timings de palavra junto, entao a legenda continua
    # sincronizada sem nenhuma conta extra do nosso lado.
    extra = {"rate": rate} if rate else {}
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary", **extra)
    word_timings = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 1e7,               # 100-ns units -> segundos
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    return word_timings


def synthesize_with_timings(text: str, voice: str, out_path: str,
                             rate: str | None = None) -> tuple[str, list[dict]]:
    """Gera o audio e retorna tambem o timing (inicio/fim em segundos) de cada
    palavra, usado para montar legendas animadas sincronizadas com a fala."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    word_timings = asyncio.run(_synthesize_with_timings(text, voice, out_path, rate))
    return out_path, word_timings
