"""Geracao das imagens das cenas.

Padrao: Cloudflare Workers AI (cota diaria gratuita, chave propria). A
Pollinations, usada antes sem chave nenhuma, passou a cobrar por imagem em
2026-09-19 ("Insufficient balance") e nao serve mais para o bot; fica aqui so
para quem tiver saldo la.
"""
import base64
import io
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

# O Flux 2 Klein aceita o vertical inteiro (256 a 1920 em cada lado), entao a
# cena sai no tamanho final do video: sem corte de lateral e sem ampliacao na
# montagem, que era de onde vinha a imagem mole. Medido lado a lado com os dois
# modelos antigos, no mesmo prompt:
#   - flux-1-schnell (cena com gente): 1024x1024 fixo, cortado para 576x1024 e
#     ampliado 1,87x. Pior: ele ignora "painterly oil texture" e devolve FOTO,
#     que e o que fazia a cena com gente parecer banco de imagem.
#   - SDXL (cena aberta): 768x1344 ampliado 1,4x, e 63s por imagem.
#   - flux-2-klein-4b: 1072x1920 nativo, pintura de verdade, mao e rosto certos,
#     18 a 30s por imagem.
# Custo e por tile de 512x512 de saida, entao dobrar a area dobra a conta. Em
# 23/09/2026, gerar 13 imagens de teste em 1080x1920 junto com dois posts do dia
# estourou os 10.000 neuronios que a Cloudflare da de graca por dia, e a terceira
# publicacao do dia ficou sem imagem. Pela conta de tras para frente, cada imagem
# naquele tamanho custou de 250 a 420 neuronios, e nao os 208 que a tabela de
# precos sugeria.
# Por isso o alvo e 1600 de altura e nao os 1920 do video: continua vertical
# NATIVO (que e o que elimina o corte de lateral), a ampliacao na montagem cai
# de 1,87x para 1,2x, e o consumo fica perto de 40% da cota, com folga para
# retentativa. Para medir de verdade um dia: o token precisa da permissao
# "Account Analytics: Read", que o atual nao tem.
# Estourar o limite no plano gratuito da ERRO, nao cobranca. Nesse caso nao
# adianta cair para os modelos antigos, porque a cota e da CONTA e nao do
# modelo: o dia inteiro fica sem imagem ate a virada.
# ATENCAO sobre a virada: a Cloudflare documenta reset diario a 00:00 UTC, mas
# nao e confiavel. Em 24/09/2026 a cota continuava recusando (429) a 01:15 UTC,
# ja no dia seguinte, e o forum da Cloudflare tem varios relatos do mesmo
# sintoma ("quota stuck after UTC reset", "dashboard shows 0/10k but API returns
# 429"). Por isso a reserva da Pollinations nao e luxo: sem ela, um dia preso
# assim tira o canal do ar inteiro.
CLOUDFLARE_MODEL_FLUX2 = "@cf/black-forest-labs/flux-2-klein-4b"
FLUX2_MAX_SIDE = 1600
# este modelo so responde a multipart/form-data: em JSON devolve 400 pedindo
# "required properties at '/' are 'multipart'"
FLUX2_STEPS = 8
# Continuidade entre cenas: a cena anterior vai como referencia visual da
# seguinte, o que mantem o MESMO cenario, a mesma luz e a mesma paleta enquanto
# a historia anda. Testado com tres cenas do tumulo de Lazaro: com referencia, a
# terceira cena manteve o tumulo, a alvenaria, o vale e a montanha da primeira,
# mudando so a pedra de lugar; sem referencia, virou um tumulo monumental com
# inscricoes em outra encosta, sem relacao com a cena 1.
# A API exige que a referencia tenha menos de 512x512 e que o campo se chame
# input_image_0 (com outro nome ela aceita a requisicao e ignora a imagem).
REF_MAX_SIDE = 480

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


def _flux2_size(width: int, height: int) -> tuple[int, int]:
    """Tamanho pedido ao Flux 2: o do video, limitado ao maximo do modelo.

    Ele arredonda por conta propria para multiplo de 16 (1080 volta como 1072),
    e o _fit acerta a diferenca depois."""
    scale = min(1.0, FLUX2_MAX_SIDE / max(1, width, height))
    return max(256, int(width * scale)), max(256, int(height * scale))


def _miniatura_referencia(path: str) -> bytes:
    """Reduz a cena anterior para caber no limite de 512x512 da referencia."""
    with Image.open(path) as img:
        pequena = img.convert("RGB")
        pequena.thumbnail((REF_MAX_SIDE, REF_MAX_SIDE), Image.LANCZOS)
        buf = io.BytesIO()
        pequena.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _cloudflare_flux2(prompt: str, width: int, height: int, seed: int,
                       referencia: str | None = None) -> bytes:
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    model = os.environ.get("CLOUDFLARE_IMAGE_MODEL_FLUX2", CLOUDFLARE_MODEL_FLUX2)
    campos = {"prompt": prompt, "width": str(width), "height": str(height),
              "steps": str(FLUX2_STEPS), "seed": str(seed)}
    # multipart: cada campo vai como parte sem nome de arquivo
    arquivos = {k: (None, v) for k, v in campos.items()}
    if referencia and os.path.exists(referencia):
        # o nome input_image_0 e exigido pela API: com outro nome ela aceita a
        # requisicao e ignora a imagem
        arquivos["input_image_0"] = ("ref.jpg", _miniatura_referencia(referencia),
                                      "image/jpeg")
    resp = requests.post(
        CLOUDFLARE_URL.format(account=account, model=urllib.parse.quote(model, safe="@/")),
        headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
        files=arquivos,
        timeout=240,
    )
    if resp.headers.get("Content-Type", "").startswith("image/"):
        resp.raise_for_status()
        return resp.content
    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise RuntimeError(f"resposta inesperada da Cloudflare: {resp.text[:200]}")
    if not data.get("success", False):
        errors = data.get("errors") or [{}]
        recado = errors[0].get("message") or str(data)[:200]
        if _e_cota(recado):
            raise CotaEsgotada(recado)
        raise RuntimeError(f"Cloudflare recusou: {recado}")
    image = (data.get("result") or {}).get("image")
    if not image:
        raise RuntimeError(f"Cloudflare nao devolveu imagem: {str(data)[:200]}")
    return base64.b64decode(image)


class CotaEsgotada(RuntimeError):
    """A cota diaria gratuita da Cloudflare acabou.

    Fica separada das outras falhas porque nao adianta tentar de novo: a cota e
    da CONTA (nao do modelo), entao nem trocar de modelo resolve, e so volta na
    virada do dia em UTC. Sem isso o bot gastava 50s por cena repetindo quatro
    vezes um erro que nunca ia passar."""


def _e_cota(mensagem: str) -> bool:
    texto = mensagem.lower()
    return "daily free allocation" in texto or "neurons" in texto


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
        if _e_cota(message):
            raise CotaEsgotada(message)
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
                          melhor_mao: bool = True, flux2: bool = True,
                          referencia: str | None = None,
                          reserva_pollinations: bool = True) -> str:
    """Gera a imagem de uma cena e devolve o caminho do arquivo.

    Ordem de tentativa: Flux 2 Klein duas vezes (vertical nativo em estilo de
    pintura, ver CLOUDFLARE_MODEL_FLUX2), depois os modelos antigos da
    Cloudflare.

    reserva_pollinations decide o que fazer quando a COTA DIARIA da Cloudflare
    acaba. Com True, o video termina na Pollinations, que e aberta e nao usa
    essa cota; a imagem dela sai bem pior e fora do estilo de pintura do canal
    (testado: pediu mulher chorando diante do tumulo e veio uma figura azul sem
    rosto, sem tumulo). Com False, a execucao para e a publicacao daquele
    horario nao sai. E escolha de dono de canal: post pior ou post nenhum.

    referencia e o caminho da imagem da cena anterior: ela entra como referencia
    visual para esta cena continuar no mesmo cenario (ver REF_MAX_SIDE). So vale
    no Flux 2; os modelos antigos ignoram.

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
    flux2_width, flux2_height = _flux2_size(width, height)
    usar_flux = provider == "cloudflare" and melhor_mao and _tem_pessoa(prompt)
    tentativas_flux2 = 2 if (flux2 and provider == "cloudflare") else 0

    last_exc = None
    sem_cota = False
    for attempt in range(retries):
        # o filtro de conteudo da Cloudflare julga a imagem PRONTA, nao o
        # prompt: com o seed fixo a nova tentativa recairia na mesma imagem
        # reprovada, entao a partir da segunda o seed muda
        tentativa_seed = seed if attempt == 0 else random.randint(1, 999_999)
        na_pollinations = sem_cota or provider != "cloudflare"
        try:
            if na_pollinations:
                content = _pollinations_image(full_prompt, gen_width, gen_height,
                                               tentativa_seed)
            elif attempt < tentativas_flux2:
                content = _cloudflare_flux2(full_prompt, flux2_width, flux2_height,
                                             tentativa_seed, referencia=referencia)
            else:
                content = _cloudflare_image(full_prompt, gen_width, gen_height,
                                             tentativa_seed, usar_flux=usar_flux)
            with open(out_path, "wb") as f:
                f.write(content)
            if na_pollinations:
                # a Pollinations assina o rodape da imagem (o nologo=true so vale
                # para conta paga), e o TikTok desqualifica da monetizacao video
                # com marca d'agua de outro app
                strip_watermark(out_path)
            _fit(out_path, width, height)
            return out_path
        except CotaEsgotada as exc:
            # nao adianta insistir nem trocar de modelo: a cota e da CONTA e so
            # volta na virada do dia
            if not reserva_pollinations:
                raise RuntimeError(
                    "A cota diaria gratuita da Cloudflare acabou, e a reserva "
                    "esta desligada (scenes.reserva_pollinations). O reset e a "
                    "00:00 UTC (21h em Brasilia), mas pode demorar mais. "
                    f"Cloudflare: {exc}"
                ) from exc
            last_exc = exc
            sem_cota = True
            print("  [images] a cota diaria gratuita da Cloudflare acabou. "
                  "O reset e a 00:00 UTC (21h em Brasilia), mas as vezes "
                  "demora mais que isso. Seguindo na Pollinations, com "
                  "imagem bem mais simples.")
        except (requests.RequestException, RuntimeError, OSError) as exc:
            last_exc = exc
            wait = 5 * (attempt + 1)
            proximo = ("de novo no Flux 2" if attempt + 1 < tentativas_flux2
                       else "no modelo antigo")
            print(f"  [images] falha ao gerar imagem (tentativa {attempt + 1}/{retries}): {exc}. "
                  f"Tentando {proximo} em {wait}s...")
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
