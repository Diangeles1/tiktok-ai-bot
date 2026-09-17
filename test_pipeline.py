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
        "narration": "Eu trabalhei doze anos na mesma padaria da esquina, "
                     "e achava que ia me aposentar ali atras do balcao.",
        "visual": "empty neighborhood bakery at dawn, bread on wooden shelves, "
                  "warm light through a dusty window",
    },
    {
        "narration": "Numa terca-feira comum, o dono chegou mais cedo, "
                     "sentou na mesa do fundo e me chamou pelo nome completo.",
        "visual": "older man sitting alone at a small cafe table in the back of a "
                  "bakery, serious expression, morning shadows",
    },
    {
        "narration": "Eu jurei que era demissao. Comecei a pensar em como contar "
                     "em casa, e nem escutei a primeira frase que ele falou.",
        "visual": "close up of worn hands holding a folded paper apron, "
                  "out of focus kitchen in the background",
    },
    {
        "narration": "Ele repetiu com calma: nao vou te demitir, eu vou vender a "
                     "padaria, e queria que voce fosse o primeiro a saber.",
        "visual": "handwritten for sale sign taped inside a bakery glass door, "
                  "quiet empty street outside",
    },
    {
        "narration": "Dois anos depois, o nome na fachada e o meu. "
                     "As vezes a pior terca-feira da sua vida esta te promovendo.",
        "visual": "new bakery storefront sign at golden hour, fresh paint, "
                  "warm inviting light spilling onto the sidewalk",
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
