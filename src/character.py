"""Gera (uma unica vez) e cacheia a imagem do personagem fixo do canal.

A mesma imagem e reaproveitada em todo video para manter a aparencia do
personagem consistente — o gerador de imagens gratuito (Pollinations.ai) nao
garante que o mesmo rosto saia igual em geracoes repetidas, entao a solucao e
gerar uma vez e guardar o arquivo (idealmente commitado no repo)."""
import os

from src.images import generate_scene_image

CHARACTER_PATH = os.path.join("assets", "character.png")


def ensure_character_image(character_cfg: dict, width: int, height: int,
                            path: str = CHARACTER_PATH, force: bool = False) -> str:
    if os.path.exists(path) and not force:
        return path

    print(f"[character] Gerando imagem de '{character_cfg['name']}' (primeira vez)...")
    generate_scene_image(
        prompt=character_cfg["description"],
        width=width,
        height=height,
        out_path=path,
        seed=character_cfg.get("seed"),
    )
    print(f"[character] Salvo em {path} — recomendado commitar esse arquivo no git "
          f"para o personagem ficar sempre igual.")
    return path
