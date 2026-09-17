"""Orquestrador: gera o roteiro, a narracao, as imagens, monta o video
e publica no TikTok. Pensado para rodar 1x/dia via GitHub Actions."""
import datetime
import os
import shutil

import yaml

from src import github_secrets, images, script_gen, tiktok_api, tts, video

OUTPUT_DIR = "output"


def load_config() -> dict:
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()
    today = datetime.date.today().isoformat()
    run_dir = os.path.join(OUTPUT_DIR, today)
    os.makedirs(run_dir, exist_ok=True)

    print(f"[1/4] Gerando roteiro sobre: {cfg['niche']}")
    script = script_gen.generate_script(
        niche=cfg["niche"],
        language=cfg["language"],
        n_scenes=cfg["video"]["scenes"],
    )
    print(f"  Tema de hoje: {script['topic']}")

    print("[2/4] Gerando narracao e imagens de cada cena")
    width, height = cfg["video"]["width"], cfg["video"]["height"]
    scene_image_paths, scene_audio_paths = [], []

    for i, scene in enumerate(script["scenes"]):
        audio_path = os.path.join(run_dir, f"scene_{i}.mp3")
        tts.synthesize_scene_audio(scene["text"], cfg["tts_voice"], audio_path)
        scene_audio_paths.append(audio_path)

        raw_img_path = os.path.join(run_dir, f"scene_{i}_raw.jpg")
        images.generate_scene_image(scene["image_prompt"], width, height, raw_img_path)

        final_img_path = os.path.join(run_dir, f"scene_{i}.jpg")
        images.burn_caption(raw_img_path, scene["text"], final_img_path)
        scene_image_paths.append(final_img_path)

    print("[3/4] Montando o video final")
    video_path = os.path.join(run_dir, "final.mp4")
    video.build_video(
        scene_image_paths, scene_audio_paths,
        width, height, cfg["video"]["fps"], video_path,
    )

    hashtags = " ".join(script.get("hashtags", []) + cfg.get("hashtags_extra", []))
    title = f"{script['caption']} {hashtags}".strip()

    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    if dry_run:
        print(f"[4/4] DRY_RUN=true — pulando publicacao. Video pronto em: {video_path}")
        print(f"  Titulo que seria usado: {title}")
        return

    print("[4/4] Publicando no TikTok")
    result = tiktok_api.post_video(
        client_key=os.environ["TIKTOK_CLIENT_KEY"],
        client_secret=os.environ["TIKTOK_CLIENT_SECRET"],
        refresh_token=os.environ["TIKTOK_REFRESH_TOKEN"],
        video_path=video_path,
        title=title,
        privacy_level=cfg.get("privacy_level", "SELF_ONLY"),
    )
    print(f"  Status: {result['status']}")

    # o refresh_token do TikTok pode rotacionar a cada uso — persiste o novo valor
    gh_pat = os.environ.get("GH_PAT")
    gh_repo = os.environ.get("GH_REPOSITORY")
    if gh_pat and gh_repo:
        github_secrets.update_repo_secret(gh_pat, gh_repo, "TIKTOK_REFRESH_TOKEN", result["new_refresh_token"])
        print("  TIKTOK_REFRESH_TOKEN atualizado no GitHub.")
    else:
        print("  AVISO: GH_PAT/GH_REPOSITORY nao configurados — o novo refresh_token "
              "NAO foi salvo. A proxima execucao vai falhar. Configure esses secrets.")

    # limpa arquivos intermediarios grandes, mantem so o video final
    for p in scene_image_paths + scene_audio_paths:
        try:
            os.remove(p)
        except OSError:
            pass


if __name__ == "__main__":
    main()
