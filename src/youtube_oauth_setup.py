"""Conecta o canal do YouTube: roda UMA vez, na sua maquina.

Pede o Client ID e o Client secret, abre o navegador para voce entrar com a
conta do canal que vai receber os Shorts e grava as chaves direto no .env e,
com GH_PAT configurado, nos Secrets do GitHub. O token nunca aparece na tela.

Pre-requisitos (ver README.md):
  1. Criar um projeto no Google Cloud Console e ativar a "YouTube Data API v3".
  2. Configurar a OAuth consent screen (External), publishing status "In production"
     (IMPORTANTE: em "Testing" o refresh_token expira em 7 dias).
  3. Criar credencial OAuth Client ID do tipo "Desktop app".

Uso:
    python -m src.youtube_oauth_setup
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from src import credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    print("Conectando o canal do YouTube.\n")
    # os dois vem da area de transferencia: colar no terminal falhava em
    # silencio ou trazia caracteres invisiveis, e o Google recusava a chave
    client_id = credentials.ask_copied(
        "Client ID", "YOUTUBE_CLIENT_ID",
        lambda v: v.endswith(".apps.googleusercontent.com") and " " not in v,
        "ele termina em .apps.googleusercontent.com")
    client_secret = credentials.ask_copied(
        "Client secret", "YOUTUBE_CLIENT_SECRET",
        lambda v: v.startswith("GOCSPX-") and " " not in v,
        "ele comeca com GOCSPX-")

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
    print("\nUm navegador vai abrir. Entre com a conta do YouTube que vai postar os Shorts.")
    print("Se aparecer 'O Google nao verificou este app', clique em 'Avancado' e depois em")
    print("'Acessar (nao seguro)': e normal para app pessoal, e quem esta logando e voce.\n")
    # prompt=consent: sem ele, quem ja autorizou antes nao recebe refresh_token
    try:
        creds = flow.run_local_server(
            port=0, prompt="consent",
            authorization_prompt_message="Se o navegador nao abrir, acesse:\n  {url}\n",
            success_message="Pronto! Pode fechar esta aba e voltar ao terminal.",
        )
    except Exception as exc:
        if "invalid_client" in str(exc):
            sys.exit("\nO Google recusou o Client ID ou o Client secret. Confira os dois "
                     "na credencial do Google Cloud e rode de novo.")
        raise
    if not creds.refresh_token:
        sys.exit("O Google nao devolveu o token de longa duracao. Rode o comando de novo.")

    credentials.save({
        "YOUTUBE_CLIENT_ID": client_id,
        "YOUTUBE_CLIENT_SECRET": client_secret,
        "YOUTUBE_REFRESH_TOKEN": creds.refresh_token,
    })
    print("\nYouTube conectado.")


if __name__ == "__main__":
    main()
