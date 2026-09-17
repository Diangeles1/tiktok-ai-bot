"""Montagem do video final: imagem fixa do personagem (com leve zoom/Ken Burns)
+ narracao + legendas animadas palavra por palavra, via MoviePy/ffmpeg."""
import os

from moviepy.editor import AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip

from src.captions import build_chunks, render_caption_png


def _ken_burns(clip, duration: float, zoom_end: float = 1.12):
    return clip.resize(lambda t: 1 + (zoom_end - 1) * (t / duration))


def build_video(character_image_path: str, audio_path: str, word_timings: list[dict],
                 width: int, height: int, fps: int, out_path: str,
                 words_per_chunk: int = 3, zoom_effect: bool = True,
                 tmp_dir: str = "output/_captions",
                 laugh_path: str | None = None, laugh_gap: float = 0.4,
                 caption_bottom_margin: int = 420) -> str:
    narration_clip = AudioFileClip(audio_path)
    narration_duration = narration_clip.duration

    if laugh_path:
        laugh_clip = AudioFileClip(laugh_path).set_start(narration_duration + laugh_gap)
        audio_clip = CompositeAudioClip([narration_clip, laugh_clip])
        duration = narration_duration + laugh_gap + laugh_clip.duration
    else:
        audio_clip = narration_clip
        duration = narration_duration

    bg = ImageClip(character_image_path).resize(height=height).set_duration(duration)
    if zoom_effect:
        bg = _ken_burns(bg, duration)
    bg = bg.set_position("center")

    caption_clips = []
    os.makedirs(tmp_dir, exist_ok=True)
    for i, chunk in enumerate(build_chunks(word_timings, words_per_chunk)):
        png_path, png_height = render_caption_png(chunk["text"], width, f"{tmp_dir}/cap_{i}.png")
        clip_duration = max(0.05, chunk["end"] - chunk["start"])
        caption_clip = (
            ImageClip(png_path)
            .set_start(chunk["start"])
            .set_duration(clip_duration)
            .set_position(("center", height - png_height - caption_bottom_margin))
        )
        caption_clips.append(caption_clip)

    final = CompositeVideoClip([bg] + caption_clips, size=(width, height)).set_audio(audio_clip)
    final = final.set_duration(duration)

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
    bg.close()
    narration_clip.close()
    for c in caption_clips:
        c.close()

    return out_path
