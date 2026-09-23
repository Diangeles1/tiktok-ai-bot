"""Geracao das imagens das cenas.

Padrao: Cloudflare Workers AI (cota diaria gratuita, chave propria). A
Pollinations, usada antes sem chave nenhuma, passou a cobrar por imagem em
2026-09-19 ("Insufficient balance") e nao serve mais para o bot; fica aqui so
para quem tiver saldo la.
"""
import base64
import os
import random
import time
import urllib.parse

import requests
from PIL import Image, ImageFont

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
CLOUDFLARE_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
CLOUDFLARE_MODEL = "@cf/stabilityai/stable-diffusion-xl-base-1.0"
# SDXL erra mao com frequencia (testado: 6 dedos numa cena de "medium shot"
# real do canal). O Flux Schnell acerta anatomia de mao e rosto muito melhor
# (testado lado a lado com o mesmo tipo de cena), mas so devolve imagem
# quadrada 1024x1024 e a Cloudflare recusa (400) qualquer campo alem de
# prompt/steps: nao aceita negative_prompt, largura/altura nem seed. Por isso
# so entra nas cenas com gente (medium shot), onde o corte central do _fit
# perde borda mas mantem quem esta no centro; a cena aberta (wide shot,
# aerial view) continua no SDXL, que aceita a proporcao vertical nativa e
# evita cortar a paisagem que o enquadramento pede.
CLOUDFLARE_MODEL_PESSOA = "@cf/black-forest-labs/flux-1-schnell"

# os modelos entregam melhor perto do tamanho em que foram treinados, e o custo
# cresce com a area: geramos ate esta altura e o video amplia na montagem
MAX_GEN_HEIGHT = 1344
# largura e altura precisam ser multiplos de 64 nos modelos de difusao
BLOCK = 64

# A Pollinations grava a marca dela no rodape das imagens: o parametro
# nologo=true so vale para contas pagas. Cortamos a faixa porque o TikTok
# desqualifica da monetizacao conteudo com marca d'agua de outro app.
WATERMARK_STRIP_RATIO = 0.05

NEGATIVE = ("text, watermark, logo, signature, frame, border, blurry, deformed hands, "
            "extra fingers, extra limbs, disfigured face, low quality")


def _provider() -> str:
    if os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"):
        return "cloudflare"
    return os.environ.get("IMAGE_PROVIDER", "pollinations")


def _gen_size(width: int, height: int) -> tuple[int, int]:
    """Tamanho de geracao: mesma proporcao, ate MAX_GEN_HEIGHT, em blocos de 64."""
    scale = min(1.0, MAX_GEN_HEIGHT / max(1, height))
    out = []
    for value in (width * scale, height * scale):
        out.append(max(BLOCK, int(round(value / BLOCK)) * BLOCK))
    return out[0], out[1]


def _tem_pessoa(prompt: str) -> bool:
    """"medium shot" e o unico dos tres enquadramentos permitidos com gente
    dentro (ver regra das cenas em src/script_gen.py): wide shot e aerial
    view sao paisagem, onde mao errada nao aparece mas cortar a lateral
    custaria a cena."""
    return "medium shot" in prompt.lower()


def _cloudflare_image(prompt: str, width: int, height: int, seed: int,
                       usar_flux: bool = False) -> bytes:
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    if usar_flux:
        # a Cloudflare recusa (400) se width/height/negative_prompt/seed forem
        # enviados para este modelo: testado, ele so aceita prompt e steps.
        # Sem seed pra fixar, cada tentativa sai de um jeito, o que aqui ate
        # ajuda: a nova tentativa depois de uma falha nao repete a mesma cena.
        model = os.environ.get("CLOUDFLARE_IMAGE_MODEL_PESSOA", CLOUDFLARE_MODEL_PESSOA)
        payload = {"prompt": prompt, "steps": 8}
    else:
        model = os.environ.get("CLOUDFLARE_IMAGE_MODEL", CLOUDFLARE_MODEL)
        payload = {"prompt": prompt, "negative_prompt": NEGATIVE, "width": width,
                   "height": height, "num_steps": 20, "seed": seed}
    resp = requests.post(
        CLOUDFLARE_URL.format(account=account, model=urllib.parse.quote(model, safe="@/")),
        headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
        json=payload,
        timeout=180,
    )
    kind = resp.headers.get("Content-Type", "")
    if kind.startswith("image/"):
        resp.raise_for_status()
        return resp.content
    # modelos como o flux-1-schnell respondem JSON com a imagem em base64
    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise RuntimeError(f"resposta inesperada da Cloudflare: {resp.text[:200]}")
    if not data.get("success", False):
        errors = data.get("errors") or [{}]
        message = errors[0].get("message") or str(data)[:200]
        raise RuntimeError(f"Cloudflare recusou: {message}")
    image = (data.get("result") or {}).get("image")
    if not image:
        raise RuntimeError(f"Cloudflare nao devolveu imagem: {str(data)[:200]}")
    return base64.b64decode(image)


def _pollinations_image(prompt: str, width: int, height: int, seed: int) -> bytes:
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt))
    resp = requests.get(url, params={"width": width, "height": height,
                                     "nologo": "true", "seed": seed}, timeout=120)
    resp.raise_for_status()
    return resp.content


def generate_scene_image(prompt: str, width: int, height: int, out_path: str,
                          seed: int | None = None, retries: int = 4,
                          melhor_mao: bool = True) -> str:
    """Gera a imagem de uma cena e devolve o caminho do arquivo.

    melhor_mao=True manda a cena com gente ("medium shot") para o Flux
    Schnell em vez do SDXL: acerta mao e rosto melhor, ao custo de vir
    quadrada e perder borda no corte do _fit (ver CLOUDFLARE_MODEL_PESSOA)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    provider = _provider()
    if provider == "cloudflare" and not os.environ.get("CLOUDFLARE_API_TOKEN"):
        raise RuntimeError("Faltam CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN para gerar imagens.")
    full_prompt = f"{prompt}, vertical composition, high detail, no text, no watermark"
    seed = seed if seed is not None else random.randint(1, 999_999)
    gen_width, gen_height = _gen_size(width, height)
    usar_flux = provider == "cloudflare" and melhor_mao and _tem_pessoa(prompt)

    last_exc = None
    for attempt in range(retries):
        try:
            if provider == "cloudflare":
                content = _cloudflare_image(full_prompt, gen_width, gen_height, seed,
                                            usar_flux=usar_flux)
            else:
                content = _pollinations_image(full_prompt, gen_width, gen_height, seed)
            with open(out_path, "wb") as f:
                f.write(content)
            if provider == "pollinations":
                strip_watermark(out_path)
            _fit(out_path, width, height)
            return out_path
        except (requests.RequestException, RuntimeError, OSError) as exc:
            last_exc = exc
            wait = 5 * (attempt + 1)
            print(f"  [images] falha ao gerar imagem (tentativa {attempt + 1}/{retries}): {exc}. "
                  f"Tentando de novo em {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Nao foi possivel gerar a imagem apos {retries} tentativas: {last_exc}")


def _fit(path: str, width: int, height: int) -> str:
    """Deixa a imagem no tamanho pedido, cortando o excesso pelo centro.

    Alguns modelos ignoram a proporcao pedida (o flux-1-schnell devolve sempre
    quadrado): sem isso a cena entraria esticada no video."""
    # o formato segue a extensao pedida: a Cloudflare responde PNG, que pesa
    # varias vezes mais que JPEG e ainda viaja no artifact do GitHub
    image_format = "JPEG" if os.path.splitext(path)[1].lower() in (".jpg", ".jpeg") else "PNG"
    with Image.open(path) as img:
        if img.size == (width, height) and (img.format or "PNG") == image_format:
            return path
        img = img.convert("RGB") if image_format == "JPEG" else img
        source_ratio = img.width / img.height
        target_ratio = width / height
        if source_ratio > target_ratio:
            new_width = int(round(img.height * target_ratio))
            box = ((img.width - new_width) // 2, 0, (img.width + new_width) // 2, img.height)
        else:
            new_height = int(round(img.width / target_ratio))
            box = (0, (img.height - new_height) // 2, img.width, (img.height + new_height) // 2)
        fitted = img.crop(box).resize((width, height), Image.LANCZOS)

    options = {"quality": 95} if image_format == "JPEG" else {}
    fitted.save(path, format=image_format, **options)
    return path


def strip_watermark(path: str, ratio: float = WATERMARK_STRIP_RATIO) -> str:
    """Corta a faixa inferior da imagem, onde fica a marca d'agua da Pollinations."""
    with Image.open(path) as img:
        # a Pollinations responde JPEG: re-salvar como PNG multiplicaria o
        # tamanho de um arquivo que fica commitado no repo
        image_format = img.format
        width, height = img.size
        cropped = img.crop((0, 0, width, int(height * (1 - ratio))))

    options = {"quality": 95} if image_format == "JPEG" else {}
    cropped.save(path, format=image_format, **options)
    return path


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
