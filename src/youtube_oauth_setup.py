"""Script de configuracao inicial: roda UMA vez, na sua maquina, para obter
o refresh_token do YouTube. Abre o navegador para voce logar com a conta do
YouTube que vai receber os Shorts.

Pre-requisitos (ver README.md):
  1. Criar um projeto no Google Cloud Console e ativar a "YouTube Data API v3".
  2. Configurar a OAuth consent screen (External), publishing status "In production"
     (IMPORTANTE: em "Testing" o refresh_token expira em 7 dias).
  3. Criar credencial OAuth Client ID do tipo "Desktop app".

Uso:
    python -m src.youtube_oauth_setup
"""
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID") or input("YOUTUBE_CLIENT_ID: ").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET") or input("YOUTUBE_CLIENT_SECRET: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    print("\nUm navegador vai abrir. Faca login com a conta do YouTube que vai postar os Shorts.")
    print("Se aparecer o aviso 'O Google não verificou este app', clique em "
          "'Avancado' > 'Acessar [nome do app] (não seguro)' — e normal para apps pessoais.\n")
    creds = flow.run_local_server(port=0)

    print("\nSucesso! Salve este valor como Secret no GitHub "
          "(Settings > Secrets and variables > Actions):\n")
    print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")


if __name__ == "__main__":
    main()
