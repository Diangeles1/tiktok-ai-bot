"""Robo que posta no TikTok pelo site, num Chrome so dele, sem ninguem clicar.

AVISO: automatizar o site vai contra os termos do TikTok. O dono do canal
decidiu usar assumindo o risco (queda do robo quando o site muda, captcha,
alcance menor, restricao ou suspensao da conta). Existe enquanto o app oficial
nao e aprovado; depois disso o caminho e o Direct Post do painel.

Login sem arquivo de cookie: o robo usa um perfil proprio do Chrome, fora do
projeto (%LOCALAPPDATA%/CandeiaBiblica/tiktok-perfil). `--login` abre esse perfil
na pagina de login e voce entra (QR code, telefone, e-mail ou Google). A sessao
fica guardada e criptografada pelo proprio Chrome, presa ao usuario do Windows.
O robo so confere se o cookie de sessao existe; nunca le, mostra ou grava o
valor. Para cortar o acesso: app do TikTok > Seguranca > Gerenciar dispositivos.

Uso (na pasta do projeto):
    python -m src.tiktok_robo --login           entra na conta (uma vez)
    python -m src.tiktok_robo --ensaio [PASTA]  preenche tudo e NAO posta
    python -m src.tiktok_robo                   baixa do GitHub e posta o que falta
"""
import argparse
import datetime
import os
import sys
import time

from src.env_file import ENV_FILE, read_env_file
from src.github_videos import AUTO_PREFIX, append_history, fetch_github_videos, read_json

OUTPUT_DIR = "output"
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?lang=en"
LOGIN_URL = "https://www.tiktok.com/login"
CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
)
# so videos recentes: com o PC desligado por dias, postar a fila inteira de
# uma vez pareceria spam e publicaria historia fora de hora
RECENT_HOURS = 36
MAX_PER_RUN = 2
LOCK_MAX_AGE = 45 * 60

# seletores da pagina de upload (TikTok Studio em ingles, forcado pelo ?lang=en)
SEL_FILE = 'input[type="file"][accept*="video"]'
SEL_CAPTION = 'div[contenteditable="true"]'
SEL_POST = 'button[data-e2e="post_video_button"]'
POSTED_TEXTS = ("Your video has been uploaded", "Video published", "Manage your posts")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(message: str) -> None:
    print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {message}", flush=True)


def profile_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "CandeiaBiblica", "tiktok-perfil")


def chrome_path() -> str:
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    raise SystemExit("Google Chrome nao encontrado. Instale o Chrome para usar o robo.")


LOGIN_QR_URL = "https://www.tiktok.com/login/qrcode"
# mensagens de erro da pagina de login que valem ir para o log (o texto da
# pagina nunca inclui o QR code nem senha)
LOGIN_ERRORS = ("Something went wrong", "Too many attempts", "Maximum number of attempts",
                "QR code expired", "try again later", "Unable to", "not available")


def _login_problem(page) -> str | None:
    try:
        text = page.locator("body").inner_text(timeout=2000)
    except Exception:
        return None
    for marker in LOGIN_ERRORS:
        index = text.lower().find(marker.lower())
        if index >= 0:
            return " ".join(text[index:index + 160].split())
    return None


def open_login(timeout: int = 30 * 60) -> None:
    """Abre o Chrome do robo na pagina de login e espera voce entrar.

    O login acontece no mesmo Chrome que depois posta: a sessao salva por um
    Chrome aberto do jeito normal nao chegou ao Chrome do robo (so os cookies
    de visitante passaram). Quem digita e voce; o robo so espera o cookie de
    sessao aparecer, sem ler o valor, e fecha a janela sozinho."""
    from playwright.sync_api import sync_playwright

    os.makedirs(profile_dir(), exist_ok=True)
    with sync_playwright() as p:
        context = _context(p)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(LOGIN_QR_URL, wait_until="domcontentloaded")
            page.bring_to_front()
            if _logged_in(context):
                log("O Chrome do robo ja esta logado no TikTok.")
                return
            log("Abri o Chrome do robo no QR code de login do TikTok.")
            log("No app do TikTok (celular): Perfil > icone de escanear > aponte para o QR.")
            log("Se o QR nao der, use outro jeito de entrar na mesma janela. Nao feche:")
            log("ela fecha sozinha quando der certo.")
            deadline = time.time() + timeout
            last_problem, last_notice = None, time.time()
            while time.time() < deadline:
                if not context.pages:
                    raise SystemExit("A janela foi fechada antes do login terminar.")
                if _logged_in(context):
                    # tempo para o Chrome gravar a sessao no disco antes de fechar
                    time.sleep(5)
                    log("LOGIN OK: o Chrome do robo esta logado no TikTok.")
                    return
                problem = _login_problem(context.pages[-1])
                if problem and problem != last_problem:
                    log(f"  a pagina do TikTok mostra: {problem}")
                    last_problem = problem
                if time.time() - last_notice > 120:
                    log("  ainda esperando o login...")
                    last_notice = time.time()
                time.sleep(3)
            raise SystemExit("O login nao terminou em 30 minutos. Rode --login de novo.")
        finally:
            context.close()


def _context(playwright):
    chrome_path()  # sem o Chrome instalado, a mensagem clara vem daqui
    try:
        return playwright.chromium.launch_persistent_context(
            profile_dir(), channel="chrome", headless=False, locale="en-US",
            viewport={"width": 1280, "height": 900},
            args=["--no-first-run", "--no-default-browser-check"],
        )
    except Exception as exc:
        # o Chrome trava o perfil enquanto ele esta aberto
        raise RuntimeError("Nao consegui abrir o Chrome do robo. Se a janela do login ainda "
                           f"estiver aberta, feche e tente de novo. ({exc})") from exc


def _logged_in(context) -> bool:
    # so confere se o cookie existe; o valor nunca sai daqui
    return any(c.get("name") == "sessionid" and c.get("value")
               for c in context.cookies("https://www.tiktok.com"))


def _post_enabled(page) -> bool:
    button = page.locator(SEL_POST).first
    if not button.count():
        return False
    return (button.get_attribute("data-disabled") == "false"
            or button.get_attribute("aria-disabled") == "false")


def _wait(condition, timeout: float, step: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def _set_caption(page, caption: str) -> None:
    box = page.locator(SEL_CAPTION).first
    box.click()
    # o TikTok preenche o nome do arquivo como legenda: apaga antes
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    for word in caption.split(" "):
        page.keyboard.type(word, delay=25)
        # a hashtag abre uma lista de sugestoes; o espaco fecha e mantem o texto
        page.keyboard.type(" ", delay=25)
        if word.startswith("#"):
            time.sleep(1.2)


def _mark_ai(page) -> bool:
    """Liga "AI-generated content" nas opcoes avancadas. Devolve se ficou ligado."""
    more = page.get_by_text("Show more", exact=True)
    if more.count() and more.first.is_visible():
        more.first.click()
        time.sleep(1)
    switch = page.locator(
        "xpath=//*[normalize-space(text())='AI-generated content']"
        "/ancestor::*[.//*[@role='switch' or (self::input and @type='checkbox')]][1]"
        "//*[@role='switch' or (self::input and @type='checkbox')]").first
    if not switch.count():
        return False

    def is_on() -> bool:
        checked = switch.get_attribute("aria-checked")
        if checked is not None:
            return checked == "true"
        return switch.is_checked()

    if not is_on():
        switch.click(force=True)
        time.sleep(1)
        # o TikTok pede confirmacao ao ligar o rotulo
        confirm = page.get_by_role("button", name="Turn on")
        if confirm.count() and confirm.first.is_visible():
            confirm.first.click()
            time.sleep(1)
    return is_on()


def _visibility(page) -> str:
    label = page.locator("xpath=//*[normalize-space(text())='Who can watch this video']"
                         "/following::*[normalize-space(text())][1]").first
    return label.inner_text().strip() if label.count() else "?"


def fill_and_post(page, video: str, caption: str, rehearsal: bool, shot: str | None) -> dict:
    page.goto(UPLOAD_URL, wait_until="domcontentloaded")
    page.locator(SEL_FILE).first.wait_for(state="attached", timeout=60_000)
    page.locator(SEL_FILE).first.set_input_files(video)
    page.locator(SEL_CAPTION).first.wait_for(timeout=180_000)
    log("  video enviado, esperando o TikTok processar")
    if not _wait(lambda: _post_enabled(page), timeout=600):
        raise RuntimeError("o TikTok nao terminou de processar o video em 10 minutos")

    _set_caption(page, caption)
    ai = False
    try:
        ai = _mark_ai(page)
    except Exception as exc:
        log(f"  AVISO: nao consegui marcar o rotulo de IA ({exc})")
    if not ai:
        log("  AVISO: o rotulo 'AI-generated content' nao ficou ligado")
    visibility = _visibility(page)
    log(f"  legenda preenchida, rotulo de IA: {'sim' if ai else 'nao'}, quem pode ver: {visibility}")
    if visibility not in ("Everyone", "?"):
        raise RuntimeError(f"'Who can watch' esta em '{visibility}', nao em Everyone. "
                           "Confira se a conta do TikTok esta publica.")

    if rehearsal:
        if shot:
            page.screenshot(path=shot, full_page=True)
        return {"ensaio": True, "rotulo_ia": ai, "quem_pode_ver": visibility}

    page.locator(SEL_POST).first.click()
    # aviso de verificacao de conteudo ("Post now") aparece as vezes
    time.sleep(3)
    now_button = page.locator("xpath=//button[.//div[text()='Post now']]")
    if now_button.count() and now_button.first.is_visible():
        now_button.first.click()

    def posted() -> bool:
        if "/tiktokstudio/content" in page.url:
            return True
        return any(page.get_by_text(text).count() for text in POSTED_TEXTS)

    if not _wait(posted, timeout=180):
        if shot:
            page.screenshot(path=shot, full_page=True)
        raise RuntimeError("cliquei em Post, mas o TikTok nao confirmou a publicacao em 3 minutos")
    return {"rotulo_ia": ai, "quem_pode_ver": visibility}


def pending_runs() -> list[str]:
    """Videos do automatico ainda nao postados no TikTok, do mais antigo ao
    mais novo, so das ultimas RECENT_HOURS horas."""
    if not os.path.isdir(OUTPUT_DIR):
        return []
    limit = time.time() - RECENT_HOURS * 3600
    runs = []
    for name in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, name)
        video = os.path.join(path, "final.mp4")
        if not name.startswith(AUTO_PREFIX) or not os.path.exists(video):
            continue
        history = read_json(os.path.join(path, "publicacao.json")) or {}
        if any(t.get("ok") for t in history.get("tiktok", [])):
            continue
        if os.path.getmtime(video) >= limit:
            runs.append((os.path.getmtime(video), name))
    return [name for _, name in sorted(runs)]


def caption_of(path: str) -> str:
    meta = read_json(os.path.join(path, "metadata.json")) or {}
    return (meta.get("legenda_tiktok")
            or " ".join([meta.get("titulo_youtube", ""), *meta.get("hashtags", [])]).strip())


class Lock:
    """Impede duas execucoes juntas (o agendador pode disparar com uma ainda
    rodando), o que postaria o mesmo video duas vezes."""

    def __init__(self):
        self.path = os.path.join(OUTPUT_DIR, ".robo_tiktok.lock")

    def __enter__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if os.path.exists(self.path) and time.time() - os.path.getmtime(self.path) < LOCK_MAX_AGE:
            raise SystemExit("Outra execucao do robo esta rodando. Saindo.")
        with open(self.path, "w") as f:
            f.write(str(os.getpid()))
        return self

    def __exit__(self, *exc):
        if os.path.exists(self.path):
            os.remove(self.path)


def run(rehearsal_folder: str | None, rehearsal: bool) -> int:
    from playwright.sync_api import sync_playwright

    if rehearsal:
        if rehearsal_folder:
            targets = [rehearsal_folder]
        else:
            # o video mais recente que existir, do automatico ou do painel
            candidates = [n for n in os.listdir(OUTPUT_DIR)
                          if os.path.exists(os.path.join(OUTPUT_DIR, n, "final.mp4"))]
            targets = sorted(candidates, key=lambda n: os.path.getmtime(
                os.path.join(OUTPUT_DIR, n, "final.mp4")))[-1:]
    else:
        result = fetch_github_videos(read_env_file(ENV_FILE), OUTPUT_DIR)
        log(f"GitHub: {result.get('novos', 0)} video(s) novo(s)"
            + (f" ({result['erro']})" if result.get("erro") else ""))
        targets = pending_runs()[:MAX_PER_RUN]
    if not targets:
        log("Nada para postar no TikTok.")
        return 0

    failures = 0
    with sync_playwright() as p:
        context = _context(p)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.tiktok.com/", wait_until="domcontentloaded")
            if not _logged_in(context):
                raise SystemExit("O Chrome do robo nao esta logado no TikTok. "
                                 "Rode: python -m src.tiktok_robo --login")
            for name in targets:
                path = os.path.join(OUTPUT_DIR, name)
                log(f"{'Ensaio' if rehearsal else 'Postando'}: {name}")
                shot = os.path.join(path, "robo_ensaio.png" if rehearsal else "robo_erro.png")
                when = datetime.datetime.now().isoformat(timespec="seconds")
                try:
                    outcome = fill_and_post(page, os.path.abspath(os.path.join(path, "final.mp4")),
                                            caption_of(path), rehearsal, shot)
                except Exception as exc:
                    failures += 1
                    log(f"  FALHOU: {exc}")
                    if not rehearsal:
                        append_history(path, "tiktok", {"ok": False, "modo": "robo",
                                                        "erro": str(exc)[:500], "quando": when})
                    continue
                if rehearsal:
                    log(f"  ENSAIO OK (nada foi postado). Print do formulario: {shot}")
                else:
                    append_history(path, "tiktok", {"ok": True, "modo": "robo", "quando": when,
                                                    "rotulo_ia": outcome["rotulo_ia"]})
                    log("  postado no TikTok")
                    time.sleep(90)  # espaco entre dois posts seguidos
        finally:
            context.close()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Robo do TikTok (posta pelo site).")
    parser.add_argument("--login", action="store_true", help="abre o Chrome do robo para entrar")
    parser.add_argument("--ensaio", nargs="?", const="", metavar="PASTA",
                        help="preenche tudo e nao posta (padrao: o video mais recente)")
    args = parser.parse_args()
    if args.login:
        open_login()
        return
    with Lock():
        sys.exit(run(args.ensaio or None, rehearsal=args.ensaio is not None))


if __name__ == "__main__":
    main()
