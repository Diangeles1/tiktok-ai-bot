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
import sys
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
    client_key = credentials.ask("Client key do app", "TIKTOK_CLIENT_KEY")
    client_secret = credentials.ask("Client secret do app", "TIKTOK_CLIENT_SECRET", secret=True)
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
    print("Depois de autorizar, a pagina de retorno mostra um 'code'. Copie e cole aqui.")
    code = urllib.parse.unquote(input("code: ").strip())

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
