"""Monta a linha de tempo das cenas: uma imagem e um trecho de narracao por
cena, com os tempos em segundos desde o inicio do video.

A narracao e sintetizada por cena (nao de uma vez), porque assim a duracao de
cada cena sai exata do proprio arquivo de audio. Cortar uma narracao unica nos
tempos das palavras erraria o ponto de troca de imagem."""
import os

from moviepy.editor import AudioFileClip

from src import personas as personas_mod, tts
from src.captions import attach_punctuation
from src.images import generate_scene_image


def render_images(scenes: list[dict], style: str, width: int, height: int,
                   out_dir: str, seed: int | None = None,
                   personas: list[dict] | None = None) -> None:
    """Gera a imagem de cada cena e guarda o caminho em scene["image"].

    O mesmo sufixo de estilo vai em todas as cenas: sem isso cada imagem sai
    com uma pegada visual diferente e o video parece uma colagem. As figuras
    biblicas citadas ganham a descricao fixa do config (src/personas.py)."""
    os.makedirs(out_dir, exist_ok=True)
    built = personas_mod.build(personas)
    for i, scene in enumerate(scenes):
        print(f"  [cena {i + 1}/{len(scenes)}] imagem: {scene['visual'][:60]}...")
        scene["image"] = generate_scene_image(
            prompt=f"{personas_mod.apply(scene['visual'], built)}, {style}",
            width=width,
            height=height,
            out_path=os.path.join(out_dir, f"scene_{i:02d}.jpg"),
            # varia o seed por cena, senao todas as imagens saem parecidas
            seed=None if seed is None else seed + i,
        )


def render_narration(scenes: list[dict], voice: str, out_dir: str, rate: str | None = None,
                      gap: float = 0.25) -> float:
    """Sintetiza a narracao de cada cena e preenche scene["audio"], ["start"],
    ["duration"] e ["timings"] (tempos absolutos). Retorna a duracao total."""
    os.makedirs(out_dir, exist_ok=True)
    cursor = 0.0

    for i, scene in enumerate(scenes):
        audio_path, timings = tts.synthesize_with_timings(
            scene["narration"], voice, os.path.join(out_dir, f"scene_{i:02d}.mp3"),
            rate=rate,
        )
        # o edge-tts devolve a palavra sem pontuacao; recuperada aqui, na
        # origem, para todo mundo que consome o timing ja receber certo
        timings = attach_punctuation(scene["narration"], timings)

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
