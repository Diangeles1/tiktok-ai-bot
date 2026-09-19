"""Montagem do video final: sequencia de cenas (imagem + narracao) com leve
zoom, legendas animadas palavra por palavra, risada e musica de fundo.

Um video de personagem fixo e so o caso de uma unica cena que dura a narracao
inteira, entao os dois formatos usam este mesmo caminho."""
import os

import numpy as np
from moviepy.audio.fx.all import audio_fadeout, audio_loop
from moviepy.editor import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                             ImageClip, VideoClip)
from PIL import Image, ImageDraw, ImageEnhance

from src.captions import build_chunks, render_chunk
from src.images import load_font


def _ease(progress: float) -> float:
    """Smoothstep: acelera e desacelera nas pontas. Movimento linear entrega que
    e interpolacao de software; com easing parece movimento de camera."""
    return progress * progress * (3 - 2 * progress)


# Movimentos de camera alternados por cena, para o video nao ficar repetitivo:
# (zoom inicial, zoom final, pan inicial, pan final), pan em fracao do excedente
# da imagem (0 = borda esquerda/topo, 0.5 = centro, 1 = borda direita/base).
CAMERA_MOVES = [
    (1.04, 1.16, (0.35, 0.50), (0.65, 0.50)),
    (1.16, 1.04, (0.65, 0.50), (0.35, 0.50)),
    (1.04, 1.16, (0.50, 0.62), (0.50, 0.38)),
    (1.16, 1.04, (0.50, 0.38), (0.50, 0.62)),
]


def _load_boosted(image_path: str, color_boost: float = 1.0) -> Image.Image:
    """Abre a imagem ja com o realce de cor aplicado.

    O gerador devolve imagem um pouco lavada e a correcao faz diferenca visivel
    no feed. Feito uma vez por cena, na abertura, e nao dentro do make_frame:
    aplicar por quadro multiplicaria o custo por 30 sem mudar o resultado."""
    source = Image.open(image_path).convert("RGB")
    if color_boost and abs(color_boost - 1.0) > 1e-3:
        source = ImageEnhance.Color(source).enhance(color_boost)
    return source


def _render_watermark(handle: str, width: int, out_path: str) -> tuple[str, int, int]:
    """Desenha o @ do canal em PNG transparente, com contorno para continuar
    legivel tanto sobre cena clara quanto escura."""
    font = load_font(max(18, int(width / 26)))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.textbbox((0, 0), handle, font=font, stroke_width=3)
    w, h = box[2] - box[0], box[3] - box[1]
    img = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((6 - box[0], 6 - box[1]), handle, font=font,
                              fill=(255, 255, 255, 255),
                              stroke_width=3, stroke_fill=(0, 0, 0, 255))
    img.save(out_path)
    return out_path, img.width, img.height


def _camera_move(image_path: str, duration: float, width: int, height: int, move: tuple,
                  color_boost: float = 1.0):
    """Ken Burns com easing: zoom e pan simultaneos sobre a imagem parada.

    Cada quadro e um recorte da imagem original redimensionado direto para o
    tamanho do video. Ampliar a imagem e reposicionar com offset seria o caminho
    obvio, mas ai qualquer erro de arredondamento no offset expoe faixa preta na
    beirada; recortando, o quadro sai sempre exato."""
    zoom_from, zoom_to, pan_from, pan_to = move
    source = _load_boosted(image_path, color_boost)
    src_w, src_h = source.size

    # maior janela com o aspecto do video que cabe na imagem, no zoom 1
    full_w = min(src_w, src_h * width / height)
    full_h = full_w * height / width

    def make_frame(t):
        progress = _ease(min(1.0, t / duration))
        zoom = zoom_from + (zoom_to - zoom_from) * progress
        win_w, win_h = full_w / zoom, full_h / zoom
        fx = pan_from[0] + (pan_to[0] - pan_from[0]) * progress
        fy = pan_from[1] + (pan_to[1] - pan_from[1]) * progress
        left = (src_w - win_w) * fx
        top = (src_h - win_h) * fy
        frame = source.resize((width, height), Image.BICUBIC,
                               box=(left, top, left + win_w, top + win_h))
        return np.asarray(frame)

    return VideoClip(make_frame, duration=duration)


def _pop(clip, canvas_w: int, canvas_h: int, center_y: float,
          duration: float = 0.14, start_scale: float = 0.84):
    """Entrada da legenda: cresce rapido ate o tamanho normal. A posicao e
    recalculada junto com a escala para o centro do texto ficar parado, senao a
    legenda escorrega pela tela enquanto cresce."""
    def scale(t):
        if t >= duration:
            return 1.0
        return start_scale + (1 - start_scale) * _ease(t / duration)

    def position(t):
        current = scale(t)
        return (canvas_w * (1 - current) / 2, center_y - canvas_h * current / 2)

    return clip.resize(scale).set_position(position)


def _build_audio(scenes: list[dict], narration_end: float, total: float,
                  laugh_path: str | None, laugh_gap: float,
                  music_path: str | None, music_volume: float) -> tuple:
    tracks = [AudioFileClip(s["audio"]).set_start(s["start"]) for s in scenes]

    if laugh_path:
        tracks.append(AudioFileClip(laugh_path).set_start(narration_end + laugh_gap))

    if music_path:
        music = AudioFileClip(music_path).volumex(music_volume)
        music = audio_loop(music, duration=total)
        tracks.append(audio_fadeout(music, min(2.0, total / 4)))

    return CompositeAudioClip(tracks), tracks


def build_video(scenes: list[dict], width: int, height: int, fps: int, out_path: str,
                 words_per_chunk: int = 3, zoom_effect: bool = True,
                 tmp_dir: str = "output/_captions",
                 laugh_path: str | None = None, laugh_gap: float = 0.4,
                 caption_bottom_margin: int = 420,
                 music_path: str | None = None, music_volume: float = 0.10,
                 crossfade: float = 0.6, color_boost: float = 1.0,
                 watermark: str | None = None, watermark_opacity: float = 0.35,
                 watermark_repeats: int = 4) -> str:
    """Cada cena precisa de "image", "audio", "start", "duration" e "timings"
    (tempos absolutos), como monta src.scenes."""
    narration_end = scenes[-1]["start"] + scenes[-1]["duration"]
    total = narration_end
    if laugh_path:
        with AudioFileClip(laugh_path) as laugh:
            total = narration_end + laugh_gap + laugh.duration

    scene_clips = []
    for i, scene in enumerate(scenes):
        is_last = i == len(scenes) - 1
        # a imagem passa do fim da propria cena para a proxima ter algo por baixo
        # durante o crossfade; a ultima estica ate o fim para a risada nao cair
        # sobre tela preta
        visual_duration = (total - scene["start"]) if is_last else (scene["duration"] + crossfade)

        if zoom_effect:
            clip = _camera_move(scene["image"], visual_duration, width, height,
                                 CAMERA_MOVES[i % len(CAMERA_MOVES)], color_boost)
        else:
            frame = np.asarray(_load_boosted(scene["image"], color_boost))
            clip = (ImageClip(frame).set_duration(visual_duration)
                    .resize(height=height).set_position("center"))

        clip = clip.set_start(scene["start"])
        if i > 0:
            clip = clip.crossfadein(crossfade)
        scene_clips.append(clip)

    caption_clips = []
    os.makedirs(tmp_dir, exist_ok=True)
    # Os blocos sao montados POR CENA. Achatar os timings de todas as cenas numa
    # lista so fazia um bloco de 3 palavras juntar o fim de uma cena com o inicio
    # da seguinte, atravessando o corte e a pausa entre elas: a legenda ficava
    # falando de uma cena por cima da imagem da outra.
    chunks = [(si, c) for si, scene in enumerate(scenes)
              for c in build_chunks(scene["timings"], words_per_chunk)]
    for i, (si, chunk) in enumerate(chunks):
        words = chunk["words"]
        paths, png_height = render_chunk([w["text"] for w in words], width,
                                          f"{tmp_dir}/cap_{si:02d}_{i:03d}")
        center_y = height - caption_bottom_margin - png_height / 2

        for j, path in enumerate(paths):
            # a palavra destacada troca quando a proxima comeca a ser falada; a
            # ultima do bloco segura ate o bloco acabar, para nao piscar na pausa
            start = words[j]["start"]
            end = words[j + 1]["start"] if j + 1 < len(words) else chunk["end"]
            clip = ImageClip(path).set_start(start).set_duration(max(0.05, end - start))
            if j == 0:
                clip = _pop(clip, width, png_height, center_y)
            else:
                clip = clip.set_position((0, center_y - png_height / 2))
            caption_clips.append(clip)

    # A marca d'agua aparece em varios pontos e troca de lugar. Repetir dificulta
    # que outro perfil baixe o video e corte a marca para repostar: tapar um
    # canto e facil, tapar quatro em posicoes diferentes estraga o video.
    watermark_clips = []
    if watermark and watermark_repeats > 0:
        wm_path, wm_w, wm_h = _render_watermark(watermark, width, f"{tmp_dir}/watermark.png")
        segment = total / watermark_repeats
        margin = width * 0.06
        for k in range(watermark_repeats):
            start = k * segment + segment * 0.15
            duration = min(4.0, segment * 0.55)
            if start + duration > total:
                break
            x = margin if k % 2 == 0 else width - wm_w - margin
            # mantida na metade de cima: embaixo ficaria por tras da legenda e
            # dentro da area que a interface do TikTok cobre
            y = height * (0.15 + 0.10 * (k % 3))
            watermark_clips.append(
                ImageClip(wm_path).set_start(start).set_duration(duration)
                .set_opacity(watermark_opacity).set_position((x, y))
                .crossfadein(0.4).crossfadeout(0.4)
            )

    audio, audio_tracks = _build_audio(scenes, narration_end, total,
                                        laugh_path, laugh_gap, music_path, music_volume)

    final = CompositeVideoClip(scene_clips + caption_clips + watermark_clips,
                                size=(width, height))
    final = final.set_audio(audio).set_duration(total)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    final.write_videofile(
        out_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )

    final.close()
    for clip in scene_clips + caption_clips + watermark_clips + audio_tracks:
        clip.close()

    return out_path
