"""Orquestrador: gera o roteiro, a narracao com timing de palavras, monta o
video e publica no TikTok e no YouTube Shorts. Pensado para rodar 1x/dia via
GitHub Actions. Cada plataforma e independente: se uma falhar, a outra ainda e
tentada.

Dois formatos, escolhidos em content_mode no config.yaml:
 - "cenas": narracao por cima de imagens que mudam (canal dark)
 - "personagem": monologo do personagem fixo, uma imagem so"""
import datetime
import json
import os

import yaml

from src import (character, github_secrets, hashtags, scenes as scenes_mod, script_gen,
                 sfx, thumbnail, tiktok_api, video, youtube_api)

OUTPUT_DIR = "output"


def load_config() -> dict:
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_scene_mode(cfg: dict, run_dir: str, width: int, height: int) -> tuple[dict, list[dict]]:
    script_cfg = cfg.get("script", {})
    hours = cfg.get("posting_hours_utc", [])
    slot = script_gen.current_slot(hours)
    slot_count = max(1, len(hours))
    seed_topic = script_gen.topic_of_the_day(
        script_cfg.get("topics", []), slot_index=slot, slot_count=slot_count,
    )
    hook = script_gen.hook_of_the_slot(
        script_cfg.get("hooks", []), slot_index=slot, slot_count=slot_count,
    )
    print(f"[1/4] Gerando roteiro em cenas (publicacao {slot + 1} de {slot_count}, "
          f"tema: {seed_topic or 'livre'}, gancho: {hook['name'] if hook else 'livre'})")
    script = script_gen.generate_scene_script(
        niche=cfg["niche"],
        language=cfg["language"],
        seed_topic=seed_topic,
        model=script_cfg.get("model", script_gen.MODEL),
        min_words=script_cfg.get("min_narration_words", script_gen.MIN_NARRATION_WORDS),
        max_words=script_cfg.get("max_narration_words", 220),
        extra_rules=script_cfg.get("extra_rules"),
        hook=hook,
    )
    script["_hook"] = hook["name"] if hook else None
    scenes = script["scenes"]
    print(f"  Tema de hoje: {script['topic']} "
          f"({script_gen.scene_word_count(script)} palavras em {len(scenes)} cenas)")

    print(f"[2/4] Gerando as {len(scenes)} imagens das cenas")
    scenes_mod.render_images(
        scenes,
        style=cfg["scenes"]["style"],
        width=width, height=height,
        out_dir=os.path.join(run_dir, "scenes"),
        seed=cfg["scenes"].get("seed"),
    )
    return script, scenes


def _build_character_mode(cfg: dict, run_dir: str, width: int, height: int) -> tuple[dict, list[dict]]:
    script_cfg = cfg.get("script", {})
    image = character.ensure_character_image(cfg["character"], width, height)

    print(f"[1/4] Gerando roteiro da esquete de: {cfg['character']['name']}")
    script = script_gen.generate_script(
        character_name=cfg["character"]["name"],
        character_vibe=cfg["character"]["description"],
        niche=cfg["niche"],
        language=cfg["language"],
        model=script_cfg.get("model", script_gen.MODEL),
        min_words=script_cfg.get("min_narration_words", script_gen.MIN_NARRATION_WORDS),
    )
    print(f"  Tema de hoje: {script['topic']} ({len(script['narration'].split())} palavras)")

    print("[2/4] Personagem fixo, nenhuma imagem nova a gerar")
    return script, [{"narration": script["narration"], "image": image}]


def main() -> None:
    cfg = load_config()
    today = datetime.date.today().isoformat()
    # o slot entra no nome da pasta porque com mais de uma publicacao por dia as
    # execucoes gravariam uma sobre a outra
    slot_suffix = script_gen.current_slot(cfg.get("posting_hours_utc", [])) + 1
    run_dir = os.path.join(OUTPUT_DIR, f"{today}_{slot_suffix}")
    os.makedirs(run_dir, exist_ok=True)

    width, height = cfg["video"]["width"], cfg["video"]["height"]
    mode = cfg.get("content_mode", "cenas")

    if mode == "cenas":
        script, scenes = _build_scene_mode(cfg, run_dir, width, height)
        scene_gap = cfg["scenes"].get("gap_seconds", 0.25)
    elif mode == "personagem":
        script, scenes = _build_character_mode(cfg, run_dir, width, height)
        scene_gap = 0.0
    else:
        raise ValueError(f"content_mode desconhecido: {mode!r} (use 'cenas' ou 'personagem')")

    print("[3/4] Gerando a narracao (com timing de cada palavra)")
    total = scenes_mod.render_narration(
        scenes, cfg["tts_voice"], os.path.join(run_dir, "narration"), gap=scene_gap,
    )
    # a contagem de palavras do roteiro e so uma estimativa; a duracao do audio
    # e o numero que decide se o video se qualifica para a monetizacao
    print(f"  Narracao de {total:.1f}s")
    if total < 60:
        print("  AVISO: abaixo de 1 minuto, nao qualifica para o TikTok Creator Rewards. "
              "Aumente script.min_narration_words no config.yaml.")

    print("[4/5] Montando o video final")
    video_path = os.path.join(run_dir, "final.mp4")
    sfx_cfg = cfg.get("sfx", {})
    captions_cfg = cfg.get("captions", {})
    video.build_video(
        scenes, width, height, cfg["video"]["fps"], video_path,
        words_per_chunk=captions_cfg.get("words_per_chunk", 3),
        zoom_effect=cfg["video"].get("zoom_effect", True),
        tmp_dir=os.path.join(run_dir, "_captions"),
        laugh_path=sfx.pick_random_laugh() if sfx_cfg.get("laugh_enabled", True) else None,
        laugh_gap=sfx_cfg.get("laugh_gap_seconds", 0.4),
        caption_bottom_margin=captions_cfg.get("bottom_margin", 420),
        music_path=sfx.pick_random_music() if sfx_cfg.get("music_enabled", True) else None,
        music_volume=sfx_cfg.get("music_volume", 0.10),
        crossfade=cfg["video"].get("crossfade_seconds", 0.4),
    )

    thumb_cfg = cfg.get("thumbnail", {})
    thumbnail_path = None
    if thumb_cfg.get("enabled", True):
        cover_text = script.get("thumbnail") or script.get("topic", "")
        thumbnail_path = thumbnail.build_thumbnail(
            scene_image=scenes[0]["image"],
            text=cover_text,
            width=width, height=height,
            out_path=os.path.join(run_dir, "thumbnail.jpg"),
            max_lines=thumb_cfg.get("max_lines", 3),
        )
        print(f"  Capa: \"{cover_text}\"")

    # as do video vem primeiro: sao elas que o YouTube exibe ao lado do titulo
    tags = hashtags.build(script.get("hashtags", []), cfg.get("hashtags_extra", []))
    tag_line = " ".join(tags)

    # o TikTok junta tudo numa legenda so. No YouTube o titulo tem 100
    # caracteres: enfiar hashtag ali corta o texto no meio e perde as ultimas,
    # entao elas vao para a descricao, de onde o YouTube ja as le.
    tiktok_title = f"{script['caption']} {tag_line}".strip()
    youtube_title = script["caption"].strip()
    youtube_description = (
        f"{script['caption']}\n\n{script.get('topic', '')}\n\n{tag_line}".strip()
    )

    # guarda o que foi usado para depois cruzar com a retencao no YouTube Studio
    # e descobrir qual estilo de gancho prende mais
    with open(os.path.join(run_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump({
            "data": today,
            "publicacao": slot + 1,
            "gancho": script.get("_hook"),
            "tema": seed_topic,
            "primeira_frase": scenes[0]["narration"],
            "duracao_segundos": round(total, 1),
            "hashtags": tags,
            "titulo_youtube": youtube_title,
        }, f, ensure_ascii=False, indent=2)

    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    if dry_run:
        print(f"[5/5] DRY_RUN=true, pulando publicacao. Video pronto em: {video_path}")
        print(f"  Gancho usado: {script.get('_hook')}")
        print(f"  Primeira frase: {scenes[0]['narration']}")
        print(f"  Hashtags ({len(tags)}): {tag_line}")
        print(f"  Titulo TikTok:  {tiktok_title}")
        print(f"  Titulo YouTube: {youtube_title} ({len(youtube_title)} caracteres)")
        return

    print("[5/5] Publicando")
    tiktok_cfg = cfg.get("tiktok", {})
    youtube_cfg = cfg.get("youtube", {})

    if tiktok_cfg.get("enabled", True):
        try:
            _post_to_tiktok(video_path, tiktok_title, tiktok_cfg)
        except Exception as exc:
            print(f"  [tiktok] FALHOU: {exc}")
    else:
        print("  [tiktok] desabilitado em config.yaml, pulando")

    if youtube_cfg.get("enabled", True):
        try:
            _post_to_youtube(video_path, youtube_title, youtube_description,
                              youtube_cfg, thumbnail_path)
        except Exception as exc:
            print(f"  [youtube] FALHOU: {exc}")
    else:
        print("  [youtube] desabilitado em config.yaml, pulando")


def _save_tiktok_refresh_token(new_token: str) -> None:
    gh_pat = os.environ.get("GH_PAT")
    gh_repo = os.environ.get("GH_REPOSITORY")
    if gh_pat and gh_repo:
        github_secrets.update_repo_secret(gh_pat, gh_repo, "TIKTOK_REFRESH_TOKEN", new_token)
        print("  [tiktok] TIKTOK_REFRESH_TOKEN atualizado no GitHub.")
    else:
        print("  [tiktok] AVISO: GH_PAT/GH_REPOSITORY nao configurados. O novo refresh_token "
              "NAO foi salvo e a proxima execucao vai falhar. Configure esses secrets.")


def _post_to_tiktok(video_path: str, title: str, tiktok_cfg: dict) -> None:
    print("  [tiktok] publicando...")
    result = tiktok_api.post_video(
        client_key=os.environ["TIKTOK_CLIENT_KEY"],
        client_secret=os.environ["TIKTOK_CLIENT_SECRET"],
        refresh_token=os.environ["TIKTOK_REFRESH_TOKEN"],
        video_path=video_path,
        title=title,
        privacy_level=tiktok_cfg.get("privacy_level", "SELF_ONLY"),
        on_token_refreshed=_save_tiktok_refresh_token,
    )
    print(f"  [tiktok] publicado (publish_id={result['publish_id']}, "
          f"status={result['status'].get('status')})")


def _post_to_youtube(video_path: str, title: str, description: str, youtube_cfg: dict,
                      thumbnail_path: str | None = None) -> None:
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
        thumbnail_path=thumbnail_path,
    )
    print(f"  [youtube] video publicado: https://youtube.com/shorts/{result['id']}")


if __name__ == "__main__":
    main()
