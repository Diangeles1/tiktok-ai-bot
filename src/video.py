"""Montagem do video final (imagens + narracao) com MoviePy/ffmpeg."""
import os

from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips


def build_video(scene_image_paths: list[str], scene_audio_paths: list[str],
                 width: int, height: int, fps: int, out_path: str) -> str:
    assert len(scene_image_paths) == len(scene_audio_paths)

    clips = []
    for img_path, audio_path in zip(scene_image_paths, scene_audio_paths):
        audio_clip = AudioFileClip(audio_path)
        # pequena folga no final da cena para nao cortar a narracao em seco
        duration = audio_clip.duration + 0.35
        img_clip = (
            ImageClip(img_path)
            .resize(height=height)
            .set_position("center")
            .set_duration(duration)
            .set_audio(audio_clip)
        )
        # garante exatamente width x height (crop/letterbox se a proporcao nao bater)
        img_clip = img_clip.on_color(size=(width, height), color=(0, 0, 0), pos="center")
        clips.append(img_clip)

    final = concatenate_videoclips(clips, method="compose")
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

    for c in clips:
        c.close()
    final.close()

    return out_path
