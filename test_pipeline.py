"""Teste manual: valida personagem + TTS com timing + legendas animadas + video
SEM depender de Groq nem do TikTok/YouTube (usa uma narracao fixa de exemplo)."""
import os

import yaml

from src import character, tts, video

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

FAKE_NARRATION = (
    "Bicho, outro dia eu tava no churrasco la em casa, todo mundo alegre, "
    "e minha mulher me pede pra eu ir comprar mais carvao. Eu falei, "
    "amor, o fogo ta bom, nao precisa. Ai o fogo apagou na hora, "
    "igualzinho tinha combinado com o carvao pra me dar vexame na frente "
    "dos convidados."
)

run_dir = "output/_test"
os.makedirs(run_dir, exist_ok=True)
width, height = cfg["video"]["width"], cfg["video"]["height"]

print("Gerando/validando personagem...")
char_path = character.ensure_character_image(cfg["character"], width, height)

print("Gerando narracao com timing de palavras...")
audio_path, timings = tts.synthesize_with_timings(FAKE_NARRATION, cfg["tts_voice"], f"{run_dir}/narration.mp3")
print(f"  {len(timings)} palavras, audio: {audio_path}")

print("Montando video final...")
out = video.build_video(
    char_path, audio_path, timings, width, height, cfg["video"]["fps"], f"{run_dir}/final.mp4",
    words_per_chunk=cfg["captions"]["words_per_chunk"], zoom_effect=cfg["video"]["zoom_effect"],
    tmp_dir=f"{run_dir}/_captions",
)
print(f"OK -> {out} ({os.path.getsize(out) / 1024:.1f} KB)")
