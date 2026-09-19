"""Orquestrador: gera o roteiro, a narracao com timing de palavras, monta o
video e publica no TikTok e no YouTube Shorts. Pensado para rodar 1x/dia via
GitHub Actions. Cada plataforma e independente: se uma falhar, a outra ainda e
tentada.

Dois formatos, escolhidos em content_mode no config.yaml:
 - "cenas": narracao por cima de imagens que mudam (canal dark)
 - "personagem": monologo do personagem fixo, uma imagem so

Uso:
  python main.py                          gera e publica
  python main.py --publicar output/PASTA  publica um video ja gerado"""
import argparse
import datetime
import json
import os
import sys

import yaml

from src import (character, hashtags, scenes as scenes_mod, script_gen,
                 sfx, thumbnail, tiktok_api, tiktok_token, video, youtube_api)
from src.env_file import ENV_FILE

OUTPUT_DIR = "output"

# o que cada plataforma precisa para publicar. Conferido antes de qualquer
# chamada de rede, para faltar chave virar uma mensagem clara e nao um KeyError
REQUIRED_ENV = {
    "tiktok": ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"),
    "youtube": ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"),
}

# No console do Windows (cp1252) um caractere fora da tabela faz o print
# levantar UnicodeEncodeError. Sem isso, uma linha de log derruba um render de
# dez minutos que ja estava quase pronto.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_config() -> dict:
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _phase(cfg: dict) -> tuple[str, dict]:
    """Devolve o nome da fase ativa e os parametros dela.

    Sem bloco "fases" no config, cai nos valores de monetizacao, que eram o
    comportamento de antes: melhor errar para o video longo do que publicar
    video curto sem querer numa conta que ja monetiza."""
    name = cfg.get("fase", "monetizacao")
    fallback = {"min_narration_words": script_gen.MIN_NARRATION_WORDS,
                "max_narration_words": 220, "min_scenes": script_gen.MIN_SCENES,
                "max_scenes": script_gen.MAX_SCENES, "min_duration_seconds": 60}
    return name, {**fallback, **cfg.get("fases", {}).get(name, {})}


def _build_scene_mode(cfg: dict, run_dir: str, width: int, height: int) -> tuple[dict, list[dict]]:
    script_cfg = cfg.get("script", {})
    phase_name, phase = _phase(cfg)
    hours = cfg.get("posting_hours_utc", [])
    slot = script_gen.current_slot(hours)
    slot_count = max(1, len(hours))
    # o painel local deixa escolher o tema na mao; sem isso vale a rotacao
    seed_topic = os.environ.get("TEMA", "").strip() or script_gen.topic_of_the_day(
        script_cfg.get("topics", []), slot_index=slot, slot_count=slot_count,
    )
    hook = script_gen.hook_of_the_slot(
        script_cfg.get("hooks", []), slot_index=slot, slot_count=slot_count,
    )
    # o arco define a ESTRUTURA da historia, o gancho define so a primeira
    # frase. Girar os dois em listas de tamanhos coprimos faz o mesmo tema
    # voltar meses depois contado de outro jeito.
    arc = script_gen.rotate_by_slot(
        script_cfg.get("arcs", []), slot_index=slot, slot_count=slot_count,
    )
    print(f"[1/5] Gerando roteiro em cenas (publicacao {slot + 1} de {slot_count}, "
          f"tema: {seed_topic or 'livre'}, gancho: {hook['name'] if hook else 'livre'}, "
          f"arco: {arc['name'] if arc else 'livre'}, fase: {phase_name})")
    script = script_gen.generate_scene_script(
        niche=cfg["niche"],
        language=cfg["language"],
        seed_topic=seed_topic,
        model=script_cfg.get("model", script_gen.MODEL),
        min_words=phase["min_narration_words"],
        max_words=phase["max_narration_words"],
        extra_rules=script_cfg.get("extra_rules"),
        hook=hook,
        arc=arc,
        min_scenes=phase["min_scenes"],
        max_scenes=phase["max_scenes"],
        cta=phase.get("cta"),
    )
    # guardados para o metadata.json, que e montado la no main()
    script["_hook"] = hook["name"] if hook else None
    script["_arc"] = arc["name"] if arc else None
    script["_seed_topic"] = seed_topic
    scenes = script["scenes"]
    print(f"  Tema de hoje: {script['topic']} "
          f"({script_gen.scene_word_count(script)} palavras em {len(scenes)} cenas)")

    print(f"[2/5] Gerando as {len(scenes)} imagens das cenas")
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

    print(f"[1/5] Gerando roteiro da esquete de: {cfg['character']['name']}")
    script = script_gen.generate_script(
        character_name=cfg["character"]["name"],
        character_vibe=cfg["character"]["description"],
        niche=cfg["niche"],
        language=cfg["language"],
        model=script_cfg.get("model", script_gen.MODEL),
        min_words=_phase(cfg)[1]["min_narration_words"],
    )
    print(f"  Tema de hoje: {script['topic']} ({len(script['narration'].split())} palavras)")

    print("[2/5] Personagem fixo, nenhuma imagem nova a gerar")
    return script, [{"narration": script["narration"], "image": image}]


def main() -> None:
    cfg = load_config()
    today = datetime.date.today().isoformat()
    # o slot entra no nome da pasta porque com mais de uma publicacao por dia as
    # execucoes gravariam uma sobre a outra
    slot_suffix = script_gen.current_slot(cfg.get("posting_hours_utc", [])) + 1
    # o painel local passa uma pasta propria para cada rodada, senao gerar duas
    # vezes no mesmo horario gravaria um video por cima do outro
    run_dir = os.environ.get("RUN_DIR") or os.path.join(OUTPUT_DIR, f"{today}_{slot_suffix}")
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

    print("[3/5] Gerando a narracao (com timing de cada palavra)")
    total = scenes_mod.render_narration(
        scenes, cfg["tts_voice"], os.path.join(run_dir, "narration"),
        rate=cfg.get("tts_rate"), gap=scene_gap,
    )
    # a contagem de palavras do roteiro e so uma estimativa; a duracao do audio
    # e o numero que decide se o video se qualifica para a monetizacao
    print(f"  Narracao de {total:.1f}s")
    phase_name, phase = _phase(cfg)
    min_duration = phase.get("min_duration_seconds", 0)
    if min_duration and total < min_duration:
        print(f"  AVISO: abaixo de {min_duration}s, nao qualifica para o TikTok Creator "
              f"Rewards. Aumente fases.{phase_name}.min_narration_words no config.yaml.")

    print("[4/5] Montando o video final")
    video_path = os.path.join(run_dir, "final.mp4")
    sfx_cfg = cfg.get("sfx", {})
    captions_cfg = cfg.get("captions", {})
    brand = cfg.get("branding", {})
    # a marca fica gravada no video: descobrir o placeholder depois de publicado
    # significa republicar tudo, entao o aviso sai antes do render
    if brand.get("watermark_enabled", True) and brand.get("handle") in (None, "", "@canal"):
        print("  AVISO: branding.handle ainda e o placeholder. Troque pelo @ real "
              "do canal no config.yaml antes de publicar.")
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
        color_boost=cfg["video"].get("color_boost", 1.0),
        watermark=(brand.get("handle") if brand.get("watermark_enabled", True) else None),
        watermark_opacity=brand.get("watermark_opacity", 0.35),
        watermark_repeats=brand.get("watermark_repeats", 4),
    )

    thumb_cfg = cfg.get("thumbnail", {})
    if thumb_cfg.get("enabled", True):
        # publish_run acha a capa pelo nome do arquivo na pasta
        cover_text = script_gen.cover_text(script, max_words=thumb_cfg.get("max_words", 6))
        thumbnail.build_thumbnail(
            scene_image=scenes[0]["image"],
            text=cover_text,
            width=width, height=height,
            out_path=os.path.join(run_dir, "thumbnail.jpg"),
            max_lines=thumb_cfg.get("max_lines", 3),
        )
        print(f"  Capa: \"{cover_text}\"")

    # as fixas do canal vem primeiro para nunca ficarem de fora do limite; a do
    # video preenche o que sobra (se repetir uma fixa, entra a seguinte)
    tags = hashtags.build(cfg.get("hashtags_extra", []), script.get("hashtags", []),
                          limit=cfg.get("hashtags_max", 4))
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
            "publicacao": slot_suffix,
            "gancho": script.get("_hook"),
            "arco": script.get("_arc"),
            "fase": phase_name,
            "tema": script.get("_seed_topic"),
            # de onde o modelo disse ter tirado a historia: conferir a
            # referencia e o jeito rapido de pegar distorcao antes do publico
            "passagem": script.get("passagem"),
            "primeira_frase": scenes[0]["narration"],
            "duracao_segundos": round(total, 1),
            "hashtags": tags,
            "titulo_youtube": youtube_title,
            "descricao_youtube": youtube_description,
            # no modo upload a legenda nao vai pela API: fica aqui para copiar
            "legenda_tiktok": tiktok_title,
        }, f, ensure_ascii=False, indent=2)

    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    if dry_run:
        print(f"[5/5] DRY_RUN=true, pulando publicacao. Video pronto em: {video_path}")
        print(f"  Gancho usado: {script.get('_hook')}")
        print(f"  Arco narrativo: {script.get('_arc')}")
        print(f"  Passagem: {script.get('passagem')}")
        print(f"  Primeira frase: {scenes[0]['narration']}")
        print(f"  Hashtags ({len(tags)}): {tag_line}")
        print(f"  Titulo TikTok:  {tiktok_title}")
        print(f"  Titulo YouTube: {youtube_title} ({len(youtube_title)} caracteres)")
        return

    # no horario automatico so entram as plataformas com automatico: true. O
    # TikTok fica de fora enquanto o app nao for aprovado: sai pelo painel
    auto = [p for p in REQUIRED_ENV if cfg.get(p, {}).get("automatico", True)]
    results = publish_run(run_dir, cfg, auto)
    # sem isso a execucao termina verde com a publicacao falhando, e ninguem
    # fica sabendo ate olhar o canal
    if any(not outcome["ok"] for outcome in results.values()):
        sys.exit(1)


def publish_run(run_dir: str, cfg: dict, platforms: list[str] | None = None) -> dict:
    """Publica um video ja gerado, lendo tudo do metadata.json da pasta.

    Separado da geracao para o painel local poder mostrar o video antes e so
    publicar depois que alguem aprovar. Devolve o resultado por plataforma e
    acumula as tentativas em publicacao.json, que e de onde o painel sabe o
    que ja saiu."""
    with open(os.path.join(run_dir, "metadata.json"), encoding="utf-8") as f:
        meta = json.load(f)
    video_path = os.path.join(run_dir, "final.mp4")
    thumb = os.path.join(run_dir, "thumbnail.jpg")
    thumbnail_path = (thumb if cfg.get("thumbnail", {}).get("enabled", True)
                      and os.path.exists(thumb) else None)

    print("[5/5] Publicando")
    results = {}
    for platform in ("tiktok", "youtube"):
        if platforms is not None and platform not in platforms:
            continue
        platform_cfg = cfg.get(platform, {})
        if not platform_cfg.get("enabled", True):
            print(f"  [{platform}] desabilitado em config.yaml, pulando")
            continue
        missing = [key for key in REQUIRED_ENV[platform] if not os.environ.get(key)]
        try:
            if missing:
                raise RuntimeError(f"faltam as chaves {', '.join(missing)}")
            # os .get cobrem pastas geradas antes desses campos irem para o
            # metadata.json: a legenda e a descricao sao remontadas do titulo
            tag_line = " ".join(meta.get("hashtags", []))
            if platform == "tiktok":
                # o painel manda aqui o que a pessoa escolheu na tela de
                # publicar (modo, legenda editada, privacidade, interacoes)
                choices = json.loads(os.environ.get("TIKTOK_POST") or "{}")
                caption = (choices.get("title")
                           or meta.get("legenda_tiktok")
                           or f"{meta['titulo_youtube']} {tag_line}".strip())
                outcome = _post_to_tiktok(video_path, caption, platform_cfg, choices)
            else:
                description = (meta.get("descricao_youtube")
                               or f"{meta['titulo_youtube']}\n\n{tag_line}".strip())
                outcome = _post_to_youtube(video_path, meta["titulo_youtube"], description,
                                           platform_cfg, thumbnail_path)
            results[platform] = {"ok": True, **outcome}
        except Exception as exc:
            print(f"  [{platform}] FALHOU: {exc}")
            results[platform] = {"ok": False, "erro": str(exc)}
        results[platform]["quando"] = datetime.datetime.now().isoformat(timespec="seconds")

    history_path = os.path.join(run_dir, "publicacao.json")
    history = {}
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)
    for platform, outcome in results.items():
        history.setdefault(platform, []).append(outcome)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return results


def _save_tiktok_refresh_token(new_token: str) -> None:
    tiktok_token.save_refresh_token(new_token, os.environ, ENV_FILE)


def _post_to_tiktok(video_path: str, title: str, tiktok_cfg: dict,
                    choices: dict | None = None) -> dict:
    """`choices` vem da tela de publicar do painel e vale mais que o config.yaml;
    no horario automatico fica vazio."""
    choices = choices or {}
    mode = choices.get("mode") or tiktok_cfg.get("mode", "direct")
    privacy = choices.get("privacy_level") or tiktok_cfg.get("privacy_level", "SELF_ONLY")
    options = {k: choices[k] for k in tiktok_api.POST_OPTIONS if k in choices}
    print("  [tiktok] publicando...")
    result = tiktok_api.post_video(
        client_key=os.environ["TIKTOK_CLIENT_KEY"],
        client_secret=os.environ["TIKTOK_CLIENT_SECRET"],
        refresh_token=os.environ["TIKTOK_REFRESH_TOKEN"],
        video_path=video_path,
        title=title,
        privacy_level=privacy,
        on_token_refreshed=_save_tiktok_refresh_token,
        mode=mode,
        options=options,
        # o painel ja renovou o token para consultar a conta: renovar de novo
        # aqui giraria o refresh_token duas vezes por publicacao
        access_token=os.environ.get("TIKTOK_ACCESS_TOKEN") or None,
    )
    if mode == "upload":
        print(f"  [tiktok] enviado para a caixa de entrada do app (publish_id={result['publish_id']}). "
              f"Abra o TikTok no celular e finalize a postagem. Legenda sugerida:")
        print(f"  {title}")
    else:
        print(f"  [tiktok] publicado (publish_id={result['publish_id']}, "
              f"status={result['status'].get('status')}, privacidade={privacy})")
    outcome = {"publish_id": result["publish_id"], "modo": mode,
               "status": result["status"].get("status")}
    if mode != "upload":
        outcome["privacidade"] = privacy
    return outcome


def _post_to_youtube(video_path: str, title: str, description: str, youtube_cfg: dict,
                      thumbnail_path: str | None = None) -> dict:
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
    url = f"https://youtube.com/shorts/{result['id']}"
    print(f"  [youtube] video publicado: {url}")
    return {"id": result["id"], "url": url}


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Gera e publica o video do canal.")
    parser.add_argument("--publicar", metavar="PASTA",
                        help="publica um video ja gerado nesta pasta, sem gerar outro")
    parser.add_argument("--plataformas", default="tiktok,youtube",
                        help="com --publicar: onde publicar, separado por virgula")
    args = parser.parse_args()
    if not args.publicar:
        main()
        return
    platforms = [p.strip() for p in args.plataformas.split(",") if p.strip()]
    unknown = sorted(set(platforms) - set(REQUIRED_ENV))
    if unknown:
        parser.error(f"plataforma desconhecida: {', '.join(unknown)}")
    results = publish_run(args.publicar, load_config(), platforms)
    # nada publicado tambem e falha: quem chamou pediu para publicar
    if not results or not all(r["ok"] for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    _cli()
