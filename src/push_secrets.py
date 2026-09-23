"""Manda as chaves do .env para os Secrets do GitHub, de onde os horarios
automaticos leem. Rode depois de conectar as contas ou de trocar uma chave
(a da Groq, por exemplo): o GitHub nao le o .env da sua maquina.

Se ainda nao houver GH_PAT, abre a pagina de criacao ja com o escopo certo e
pede para colar o token, que vai direto para o .env.

Uso:
    python -m src.push_secrets
    python -m src.push_secrets --conta-cloudflare --token-cloudflare
    python -m src.push_secrets --gemini
"""
import sys
import webbrowser

from src import credentials
from src.env_file import ENV_FILE, update_env_file


# troca de chave sem terminal: a pessoa copia a chave nova no site e pronto.
# A chave atual e ignorada, para uma copia velha nao passar por nova (foi assim
# que o secret antigo do YouTube, ainda visivel no terminal, voltou para o .env)
NEW_KEYS = {
    "--nova-groq": ("GROQ_API_KEY", "chave nova da Groq",
                    lambda v: v.startswith("gsk_") and len(v) > 30),
    # a Cloudflare gera as imagens das cenas (cota diaria gratuita). O Account
    # ID aparece no painel; o token so na hora em que e criado.
    "--conta-cloudflare": ("CLOUDFLARE_ACCOUNT_ID", "Account ID da Cloudflare",
                           lambda v: len(v) == 32 and all(c in "0123456789abcdef" for c in v.lower())),
    "--token-cloudflare": ("CLOUDFLARE_API_TOKEN", "token da API da Cloudflare",
                           lambda v: 30 <= len(v) <= 80),
    "--novo-secret-youtube": ("YOUTUBE_CLIENT_SECRET", "Client secret novo do YouTube",
                              lambda v: v.startswith("GOCSPX-") and len(v) > 20),
    # roteiro alternativo ao da Groq, testado em 2026-09-23 (ver src/script_gen.py).
    # O formato da chave do AI Studio varia (viu-se tanto "AIza..." quanto
    # "AQ...."), entao o teste e so por tamanho e ausencia de espaco, como o da
    # Cloudflare.
    "--gemini": ("GEMINI_API_KEY", "chave da API do Gemini",
                 lambda v: 20 <= len(v) <= 80),
}

GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


def _replace_key(env_key: str, label: str, looks_right) -> None:
    old = credentials.current(env_key)
    key = credentials.wait_copied(label, lambda v: looks_right(v) and " " not in v,
                                  ignore={old}, accept_current=True)
    update_env_file(ENV_FILE, env_key, key)
    credentials._clipboard(clear=True)
    print(f"{label} salvo no .env (termina em {key[-4:]}).")


def main() -> None:
    for flag, (env_key, label, looks_right) in NEW_KEYS.items():
        if flag in sys.argv:
            if flag == "--gemini":
                print("Abrindo o Google AI Studio para criar a chave gratuita da Gemini.")
                print(f"Se nao abrir: {GEMINI_KEY_URL}\n")
                webbrowser.open(GEMINI_KEY_URL)
            _replace_key(env_key, label, looks_right)
    if not credentials.current("GH_PAT"):
        print("Falta o GH_PAT, o token que deixa gravar nos Secrets do GitHub.")
        print("Abrindo a pagina de criacao com o escopo 'repo' ja marcado. Escolha uma")
        print("validade longa, clique em 'Generate token', copie e cole aqui.")
        print(f"Se nao abrir: {credentials.PAT_URL}\n")
        webbrowser.open(credentials.PAT_URL)
        pat = credentials.ask("GH_PAT", "GH_PAT", secret=True)
        update_env_file(ENV_FILE, "GH_PAT", pat)
        print("GH_PAT salvo no .env.")

    values = {key: credentials.current(key) for key in credentials.WORKFLOW_SECRETS}
    present = {key: value for key, value in values.items() if value}
    missing = [key for key, value in values.items() if not value]
    if not credentials.push_to_github(present):
        sys.exit(1)
    if missing:
        print(f"Ainda faltam no .env: {', '.join(missing)}")


if __name__ == "__main__":
    main()
