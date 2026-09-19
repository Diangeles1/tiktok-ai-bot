"""Conecta a conta do TikTok: roda UMA vez, na sua maquina. Depois disso o bot
renova o token sozinho.

Pede o client key e o client secret do app (TikTok for Developers > seu app),
abre o navegador para voce autorizar com a conta que vai postar e grava as
chaves direto no .env e, com GH_PAT configurado, nos Secrets do GitHub. O
token nunca aparece na tela.

O TikTok exige redirect_uri HTTPS cadastrado no app (nao aceita localhost). O
padrao e a pagina docs/oauth-callback.html deste repo no GitHub Pages, deduzida
do endereco do repositorio; TIKTOK_REDIRECT_URI no .env troca por outra.

Uso:
    python -m src.oauth_setup
"""
import os
import re
import sys
import time
import urllib.parse
import webbrowser

import requests
import yaml

from src import credentials

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"


def _scopes() -> str:
    """Pede so o que o modo configurado usa: escopo pedido e nao habilitado no
    app faz o TikTok recusar a autorizacao inteira."""
    if os.environ.get("TIKTOK_SCOPES"):
        return os.environ["TIKTOK_SCOPES"]
    try:
        with open("config.yaml", encoding="utf-8") as f:
            mode = (yaml.safe_load(f).get("tiktok") or {}).get("mode", "direct")
    except OSError:
        mode = "direct"
    # upload: caixa de entrada (video.upload). direct: publica sozinho (video.publish)
    return "user.info.basic,video.upload" + (",video.publish" if mode == "direct" else "")


def _redirect_uri() -> str:
    explicit = credentials.current("TIKTOK_REDIRECT_URI")
    if explicit:
        return explicit
    repo = credentials.github_repo()
    if repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}/oauth-callback.html"
    return input("Redirect URI (HTTPS, o mesmo cadastrado no app do TikTok): ").strip()


def _wait_credentials(timeout: int = 1200) -> tuple[str, str]:
    """Acha o client key e o secret em qualquer texto copiado da pagina do app.

    Selecionar na pagina costuma levar junto o rotulo ("Client key ...") ou as
    duas chaves de uma vez; em vez de exigir a chave pura, procura dentro do
    texto: o key do TikTok comeca com "aw" (ou "sbaw" no sandbox) e o secret
    tem 32 caracteres. O que ja estiver copiado quando o script comeca vale."""
    print("Esperando voce copiar o Client key e o Client secret "
          "(um de cada vez ou os dois juntos)...", flush=True)
    key = secret = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        for token in re.findall(r"[A-Za-z0-9]{10,40}", credentials._clipboard()):
            if key is None and re.fullmatch(r"(?:sb)?aw[A-Za-z0-9]{10,22}", token):
                key = token
                print(f"  Client key recebido ({len(key)} caracteres).", flush=True)
            elif secret is None and len(token) >= 30 and token != key:
                secret = token
                print(f"  Client secret recebido ({len(secret)} caracteres).", flush=True)
        if key and secret:
            return key, secret
        time.sleep(1)
    raise SystemExit("As chaves nao foram copiadas em 20 minutos. Rode de novo.")


def _display_name(access_token: str) -> str | None:
    """Nome da conta autorizada, para confirmar que foi a conta certa."""
    try:
        resp = requests.get(USER_INFO_URL, params={"fields": "display_name"},
                            headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        return resp.json()["data"]["user"]["display_name"]
    except Exception:
        return None


def main() -> None:
    print("Conectando a conta do TikTok.\n")
    # da area de transferencia, como no YouTube: colar no terminal falha aqui.
    # Com --sem-terminal nem Enter e preciso: o script espera a copia sozinho
    sem_terminal = "--sem-terminal" in sys.argv
    is_key = lambda v: v.isalnum() and 10 <= len(v) <= 40
    if sem_terminal:
        client_key, client_secret = _wait_credentials()
    else:
        client_key = credentials.ask_copied(
            "Client key", "TIKTOK_CLIENT_KEY", is_key, "so letras e numeros, uns 18 caracteres")
        client_secret = credentials.ask_copied(
            "Client secret", "TIKTOK_CLIENT_SECRET",
            lambda v: v.isalnum() and len(v) >= 20 and v != client_key,
            "so letras e numeros, uns 32 caracteres, diferente do Client key")
    redirect_uri = _redirect_uri()
    scopes = _scopes()

    params = {
        "client_key": client_key,
        "scope": scopes,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "setup",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    print(f"\nEndereco de retorno: {redirect_uri}")
    print("  (precisa estar cadastrado exatamente assim no app, em Login Kit > Redirect URI)")
    print(f"Permissoes pedidas: {scopes}")
    print("\nAbrindo o navegador. Entre com a conta do TikTok que vai postar e autorize.")
    print(f"Se o navegador nao abrir, copie este endereco:\n  {auth_url}\n")
    webbrowser.open(auth_url)
    print("Depois de autorizar, a pagina de retorno mostra um 'code'.")
    # o code vale uma vez so e nunca e gravado: a chave abaixo nao existe no
    # .env, entao nao ha "valor salvo" para reaproveitar por engano
    is_code = lambda v: len(v) > 20 and " " not in v and v not in (client_key, client_secret)
    if sem_terminal:
        code = credentials.wait_copied("code", is_code, ignore={client_key, client_secret})
    else:
        code = credentials.ask_copied("code", "TIKTOK_OAUTH_CODE", is_code,
                                      "o texto longo que aparece na pagina de retorno")
    code = urllib.parse.unquote(code)

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if "refresh_token" not in data:
        # so os campos de erro: a resposta de sucesso teria tokens
        reason = data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}"
        sys.exit(f"\nO TikTok recusou: {reason}\n"
                 "O code vale poucos minutos e so uma vez: rode o comando de novo e cole o "
                 "code logo depois de autorizar.")

    credentials._clipboard(clear=True)   # o code e as chaves nao ficam no Ctrl+V
    name = _display_name(data["access_token"])
    credentials.save({
        "TIKTOK_CLIENT_KEY": client_key,
        "TIKTOK_CLIENT_SECRET": client_secret,
        "TIKTOK_REFRESH_TOKEN": data["refresh_token"],
    })
    print(f"\nTikTok conectado{f' na conta {name}' if name else ''}. "
          f"Permissoes liberadas: {data.get('scope', scopes)}")


if __name__ == "__main__":
    main()
