"""Guarda as chaves das plataformas sem que elas aparecam na tela.

Os scripts de login chamam save() no fim: o valor vai direto para o .env (que o
painel e a linha de comando usam) e, com GH_PAT configurado, para os Secrets
do repositorio (que os horarios automaticos usam)."""
import getpass
import os
import re
import subprocess
import time

from src import github_secrets
from src.env_file import ENV_FILE, read_env_file, update_env_file

# os mesmos nomes que .github/workflows/daily-post.yml le dos Secrets
WORKFLOW_SECRETS = (
    "GROQ_API_KEY",
    "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN",
    "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
    "GH_PAT",
)
PAT_URL = "https://github.com/settings/tokens/new?scopes=repo&description=tiktok-ai-bot"


def current(key: str) -> str:
    """Valor salvo no .env, ou no ambiente se o .env nao tiver."""
    return read_env_file(ENV_FILE).get(key) or os.environ.get(key, "")


def _clean_paste(value: str) -> str:
    """Tira o que alguns terminais colam junto sem aparecer: as marcas de inicio
    e fim de colagem (ESC[200~ e ESC[201~) e outros caracteres de controle.
    Com elas o valor chega errado e o Google recusa a chave como invalida."""
    value = re.sub(r"\x1b\[[0-9;]*[~A-Za-z]", "", value)
    return "".join(ch for ch in value if ch.isprintable()).strip()


def ask(label: str, key: str, secret: bool = False) -> str:
    """Pergunta um valor no terminal. Enter mantem o que ja esta no .env."""
    saved = current(key)
    hint = " (Enter mantem o que ja esta salvo)" if saved else ""
    # no Git Bash o getpass nao consegue esconder a digitacao e trava
    if secret and not os.environ.get("MSYSTEM"):
        value = getpass.getpass(f"{label}{hint}. O que voce colar nao aparece na tela: ")
        if not value.strip() and not saved:
            # alguns terminais (o embutido em apps, por exemplo) nao repassam o
            # colar para a digitacao escondida, e o valor chega vazio
            print("Nao recebi nada: este terminal nao deixa colar escondido. Cole de novo,")
            print("desta vez vai aparecer na tela. No final, rode cls para limpar.")
            value = input(f"{label}: ")
    else:
        value = input(f"{label}{hint}: ")
    value = _clean_paste(value) or saved
    if not value:
        raise SystemExit(f"Sem {label}, nao da para continuar.")
    return value


def _win_clipboard(clear: bool) -> str:
    """Area de transferencia pela API do Windows. O tkinter nao serve para
    ler de novo depois de limpar: ele passa a se achar dono do conteudo e
    devolve vazio para sempre, mesmo com outro programa copiando por cima."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    for _ in range(10):   # outro programa pode estar com ela aberta por um instante
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return ""
    try:
        if clear:
            user32.EmptyClipboard()
            return ""
        handle = user32.GetClipboardData(13)   # CF_UNICODETEXT
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _clipboard(clear: bool = False) -> str:
    """Le (ou limpa) a area de transferencia do sistema. Vazio se nao der."""
    if os.name == "nt":
        try:
            return _win_clipboard(clear)
        except Exception:
            return ""
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        try:
            if clear:
                root.clipboard_clear()
                root.update()
                return ""
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception:
        return ""


def ask_copied(label: str, key: str, looks_right, hint_format: str) -> str:
    """Pega o valor pela area de transferencia: a pessoa clica em copiar no
    site e aperta Enter. Nada e colado no terminal, entao nada aparece na tela
    nem depende do terminal aceitar colagem (varios nao aceitam)."""
    saved = current(key)
    for _ in range(3):
        extra = " (ou so Enter para manter o que ja esta salvo)" if saved else ""
        input(f"Copie o {label} no site (botao de copiar) e aperte Enter aqui{extra}.")
        value = _clean_paste(_clipboard())
        if looks_right(value):
            if value != saved:
                _clipboard(clear=True)   # a chave nao fica esquecida no Ctrl+V
            print(f"  {label} recebido ({len(value)} caracteres).")
            return value
        if saved:
            # nada copiado, ou copiado outra coisa (a proxima chave, por exemplo,
            # que fica intacta para a proxima pergunta): vale o que ja esta salvo
            print(f"  Usando o {label} que ja estava salvo.")
            return saved
        print(f"  O que esta copiado nao parece o {label} ({hint_format}). Copie de novo.")
    raise SystemExit(f"Nao consegui pegar o {label}. Rode o comando de novo.")


def wait_copied(label: str, looks_right, ignore=(), timeout: int = 1200,
                accept_current: bool = False) -> str:
    """Espera a pessoa copiar o valor no site, sem precisar de terminal: olha a
    area de transferencia a cada segundo ate aparecer algo com o formato certo.
    Por padrao o que ja estava copiado antes de comecar e descartado; com
    accept_current, vale se ja tiver o formato certo (a pessoa copiou antes)."""
    print(f"Esperando voce copiar: {label}...", flush=True)
    skip = {""} | set(ignore)
    already = _clean_paste(_clipboard())
    if accept_current and already and already not in skip and looks_right(already):
        print(f"  Recebido: {label} ({len(already)} caracteres).", flush=True)
        return already
    # limpa em vez de so ignorar o que estava copiado: se a pessoa ja tinha
    # copiado o valor certo antes, copiar de novo nao mudaria nada e o script
    # ficaria esperando para sempre
    _clipboard(clear=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = _clean_paste(_clipboard())
        if value and value not in skip and looks_right(value):
            print(f"  Recebido: {label} ({len(value)} caracteres).", flush=True)
            return value
        time.sleep(1)
    raise SystemExit(f"Nenhum {label} copiado em {timeout // 60} minutos. Rode de novo.")


def github_repo() -> str | None:
    """usuario/repo, do GH_REPOSITORY ou deduzido do endereco do git."""
    repo = current("GH_REPOSITORY")
    if repo and "seu-usuario" not in repo:
        return repo
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                             text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def push_to_github(values: dict) -> bool:
    """Grava as chaves nos Secrets do repositorio. Devolve se conseguiu."""
    pat = current("GH_PAT")
    repo = github_repo()
    if not pat or not repo:
        print("\nOs horarios automaticos leem as chaves dos Secrets do GitHub, e para")
        print("grava-las la falta o GH_PAT. Quando quiser, rode:  python -m src.push_secrets")
        return False
    try:
        for key, value in values.items():
            github_secrets.update_repo_secret(pat, repo, key, value)
    except Exception as exc:
        print(f"\nNao consegui gravar nos Secrets do GitHub: {exc}")
        print("Confira se o GH_PAT tem o escopo 'repo' e rode:  python -m src.push_secrets")
        return False
    print(f"Salvo nos Secrets do GitHub ({repo}): {', '.join(values)}")
    return True


def save(values: dict) -> None:
    """Grava no .env e tenta os Secrets do GitHub. Nunca mostra os valores."""
    for key, value in values.items():
        update_env_file(ENV_FILE, key, value)
    print(f"\nSalvo no .env: {', '.join(values)}")
    push_to_github(values)
