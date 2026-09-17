"""Teste manual do formato em cenas: valida geracao de imagens, TTS com timing,
legendas animadas, transicoes, musica e montagem final. Usa um roteiro fixo de
exemplo, entao NAO depende da Groq nem publica em nenhuma plataforma."""
import os

import yaml

from src import scenes as scenes_mod, sfx, video

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

FAKE_SCENES = [
    {
        "narration": "Um homem passou anos construindo um barco gigante "
                     "em terra seca, longe de qualquer rio ou mar.",
        "visual": "enormous unfinished wooden ship on dry cracked ground, "
                  "scaffolding of rough timber, harsh midday sun, dust in the air",
    },
    {
        "narration": "A vizinhanca inteira ria. Alguns paravam o trabalho "
                     "so pra assistir e fazer piada do velho e da sua loucura.",
        "visual": "silhouettes of villagers gathered at a distance under an "
                  "ancient stone archway, looking toward the horizon, long shadows",
    },
    {
        "narration": "Ele nao discutia. Continuava cortando madeira, "
                     "medindo, vedando cada fresta, dia depois de dia.",
        "visual": "section of a large wooden hull under construction, thick planks "
                  "sealed with dark pitch, wooden mallet and bucket of tar on the "
                  "ground, medium shot, no people",
    },
    {
        "narration": "Entao o ceu mudou de cor. O primeiro pingo caiu "
                     "e ninguem mais achou graca nenhuma.",
        "visual": "heavy dark storm clouds rolling over a desert valley, first "
                  "rain streaks catching the last light, dramatic sky",
    },
    {
        "narration": "As vezes obedecer parece loucura enquanto o ceu esta limpo. "
                     "A chuva so mostra quem estava certo depois.",
        "visual": "single shaft of golden light breaking through dark clouds over "
                  "calm water, distant ark silhouette, reverent atmosphere",
    },
]

run_dir = "output/_test"
os.makedirs(run_dir, exist_ok=True)
width, height = cfg["video"]["width"], cfg["video"]["height"]
sfx_cfg = cfg.get("sfx", {})

print(f"Gerando as {len(FAKE_SCENES)} imagens das cenas...")
scenes_mod.render_images(
    FAKE_SCENES, style=cfg["scenes"]["style"], width=width, height=height,
    out_dir=f"{run_dir}/scenes", seed=cfg["scenes"].get("seed"),
)

print("Gerando narracao por cena (com timing de palavras)...")
total = scenes_mod.render_narration(
    FAKE_SCENES, cfg["tts_voice"], f"{run_dir}/narration",
    gap=cfg["scenes"].get("gap_seconds", 0.25),
)
print(f"  narracao total: {total:.1f}s")

music_path = sfx.pick_random_music() if sfx_cfg.get("music_enabled", True) else None
print(f"  musica: {music_path or 'nenhuma (assets/music vazia)'}")

print("Montando video final...")
out = video.build_video(
    FAKE_SCENES, width, height, cfg["video"]["fps"], f"{run_dir}/final.mp4",
    words_per_chunk=cfg["captions"]["words_per_chunk"],
    zoom_effect=cfg["video"]["zoom_effect"],
    tmp_dir=f"{run_dir}/_captions",
    laugh_path=sfx.pick_random_laugh() if sfx_cfg.get("laugh_enabled", True) else None,
    laugh_gap=sfx_cfg.get("laugh_gap_seconds", 0.4),
    caption_bottom_margin=cfg["captions"].get("bottom_margin", 420),
    music_path=music_path,
    music_volume=sfx_cfg.get("music_volume", 0.10),
    crossfade=cfg["video"].get("crossfade_seconds", 0.4),
)
print(f"OK -> {out} ({os.path.getsize(out) / 1024:.1f} KB)")
