"""Orquestrador: gera o roteiro da esquete, a narracao com timing de palavras,
monta o video (personagem fixo + zoom + legendas animadas) e publica no
TikTok e no YouTube Shorts. Pensado para rodar 1x/dia via GitHub Actions.
Cada plataforma e independente: se uma falhar, a outra ainda e tentada."""
import datetime
import os

import yaml

from src import character, github_secrets, script_gen, sfx, tiktok_api, tts, video, youtube_api

OUTPUT_DIR = "output"


def load_config() -> dict:
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()
    today = datetime.date.today().isoformat()
    run_dir = os.path.join(OUTPUT_DIR, today)
    os.makedirs(run_dir, exist_ok=True)

    width, height = cfg["video"]["width"], cfg["video"]["height"]
    character_image_path = character.ensure_character_image(cfg["character"], width, height)

    print(f"[1/4] Gerando roteiro da esquete de: {cfg['character']['name']}")
    script = script_gen.generate_script(
        character_name=cfg["character"]["name"],
        character_vibe=cfg["character"]["description"],
        niche=cfg["niche"],
        language=cfg["language"],
    )
    print(f"  Tema de hoje: {script['topic']}")

    print("[2/4] Gerando narracao (com timing de cada palavra)")
    audio_path, word_timings = tts.synthesize_with_timings(
        script["narration"], cfg["tts_voice"], os.path.join(run_dir, "narration.mp3"),
    )

    print("[3/4] Montando o video final (personagem + zoom + legendas + risada)")
    video_path = os.path.join(run_dir, "final.mp4")
    sfx_cfg = cfg.get("sfx", {})
    laugh_path = sfx.pick_random_laugh() if sfx_cfg.get("laugh_enabled", True) else None
    video.build_video(
        character_image_path, audio_path, word_timings,
        width, height, cfg["video"]["fps"], video_path,
        words_per_chunk=cfg.get("captions", {}).get("words_per_chunk", 3),
        zoom_effect=cfg["video"].get("zoom_effect", True),
        tmp_dir=os.path.join(run_dir, "_captions"),
        laugh_path=laugh_path,
        laugh_gap=sfx_cfg.get("laugh_gap_seconds", 0.4),
    )

    hashtags = " ".join(script.get("hashtags", []) + cfg.get("hashtags_extra", []))
    title = f"{script['caption']} {hashtags}".strip()
    description = f"{script['caption']}\n\n{script.get('topic', '')}\n\n{hashtags}".strip()

    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    if dry_run:
        print(f"[4/4] DRY_RUN=true — pulando publicacao. Video pronto em: {video_path}")
        print(f"  Titulo que seria usado: {title}")
        return

    print("[4/4] Publicando")
    tiktok_cfg = cfg.get("tiktok", {})
    youtube_cfg = cfg.get("youtube", {})

    if tiktok_cfg.get("enabled", True):
        try:
            _post_to_tiktok(video_path, title, tiktok_cfg)
        except Exception as exc:
            print(f"  [tiktok] FALHOU: {exc}")
    else:
        print("  [tiktok] desabilitado em config.yaml, pulando")

    if youtube_cfg.get("enabled", True):
        try:
            _post_to_youtube(video_path, title, description, youtube_cfg)
        except Exception as exc:
            print(f"  [youtube] FALHOU: {exc}")
    else:
        print("  [youtube] desabilitado em config.yaml, pulando")


def _post_to_tiktok(video_path: str, title: str, tiktok_cfg: dict) -> None:
    print("  [tiktok] publicando...")
    result = tiktok_api.post_video(
        client_key=os.environ["TIKTOK_CLIENT_KEY"],
        client_secret=os.environ["TIKTOK_CLIENT_SECRET"],
        refresh_token=os.environ["TIKTOK_REFRESH_TOKEN"],
        video_path=video_path,
        title=title,
        privacy_level=tiktok_cfg.get("privacy_level", "SELF_ONLY"),
    )
    print(f"  [tiktok] status: {result['status']}")

    # o refresh_token do TikTok pode rotacionar a cada uso — persiste o novo valor
    gh_pat = os.environ.get("GH_PAT")
    gh_repo = os.environ.get("GH_REPOSITORY")
    if gh_pat and gh_repo:
        github_secrets.update_repo_secret(gh_pat, gh_repo, "TIKTOK_REFRESH_TOKEN", result["new_refresh_token"])
        print("  [tiktok] TIKTOK_REFRESH_TOKEN atualizado no GitHub.")
    else:
        print("  [tiktok] AVISO: GH_PAT/GH_REPOSITORY nao configurados — o novo refresh_token "
              "NAO foi salvo. A proxima execucao vai falhar. Configure esses secrets.")


def _post_to_youtube(video_path: str, title: str, description: str, youtube_cfg: dict) -> None:
    print("  [youtube] publicando...")
    result = youtube_api.upload_short(
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        video_path=video_path,
        title=title,
        description=description,
        category_id=youtube_cfg.get("category_id", "24"),
        privacy_status=youtube_cfg.get("privacy_status", "public"),
        made_for_kids=youtube_cfg.get("made_for_kids", False),
    )
    print(f"  [youtube] video publicado: https://youtube.com/shorts/{result['id']}")


if __name__ == "__main__":
    main()
