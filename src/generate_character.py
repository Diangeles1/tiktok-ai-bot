"""Gera (ou regenera) a imagem do personagem fixo do canal.

Uso:
    python -m src.generate_character            # gera so se ainda nao existir
    python -m src.generate_character --force     # forca gerar uma imagem nova
"""
import sys

import yaml

from src.character import ensure_character_image


def main() -> None:
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    force = "--force" in sys.argv
    path = ensure_character_image(
        cfg["character"], cfg["video"]["width"], cfg["video"]["height"], force=force,
    )
    print(f"\nPersonagem pronto em: {path}")
    print("Rode `git add assets/character.png` e commite pra fixar essa aparencia.")


if __name__ == "__main__":
    main()
