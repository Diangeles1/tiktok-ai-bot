"""Script de configuracao inicial: roda UMA vez, na sua maquina, para obter
o primeiro refresh_token do TikTok. Depois disso o bot renova o token sozinho.

O TikTok exige que o redirect_uri seja HTTPS e esteja registrado no app
(nao aceita localhost/http). O jeito mais simples e usar uma pagina estatica
no GitHub Pages deste mesmo repo (ver docs/oauth-callback.html) como redirect_uri,
por exemplo: https://seu-usuario.github.io/tiktok-ai-bot/oauth-callback.html

Uso:
    python -m src.oauth_setup
"""
import os
import urllib.parse

import requests

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
# video.upload serve o modo "upload" (caixa de entrada) e video.publish o modo
# "direct". Os dois precisam estar habilitados no app do TikTok Developer
# Portal; se so um estiver, defina TIKTOK_SCOPES com a lista que o app tem.
SCOPES = os.environ.get("TIKTOK_SCOPES", "user.info.basic,video.upload,video.publish")


def main() -> None:
    client_key = os.environ.get("TIKTOK_CLIENT_KEY") or input("TIKTOK_CLIENT_KEY: ").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET") or input("TIKTOK_CLIENT_SECRET: ").strip()
    redirect_uri = os.environ.get("TIKTOK_REDIRECT_URI") or input(
        "Redirect URI (HTTPS, ja cadastrado no app do TikTok Developer Portal): "
    ).strip()

    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "setup",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    print("\n1) Abra esta URL no navegador e autorize o app com a conta do TikTok que vai postar:")
    print(f"\n   {auth_url}\n")
    print("2) Voce sera redirecionado para o redirect_uri com '?code=...&state=setup' na URL.")
    print("   Copie o valor do parametro 'code' (esta URL-encoded).\n")

    code = input("Cole aqui o valor de 'code': ").strip()
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
    resp.raise_for_status()
    data = resp.json()

    if "refresh_token" not in data:
        print("\nErro ao trocar o code por tokens:")
        print(data)
        return

    print("\nSucesso! Salve estes valores como Secrets no GitHub "
          "(Settings > Secrets and variables > Actions):\n")
    print(f"TIKTOK_REFRESH_TOKEN = {data['refresh_token']}")
    print(f"\n(access_token valido por {data['expires_in']}s, refresh_token valido por {data['refresh_expires_in']}s)")


if __name__ == "__main__":
    main()
