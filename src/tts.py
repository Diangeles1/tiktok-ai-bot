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
