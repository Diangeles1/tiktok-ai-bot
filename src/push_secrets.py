"""Manda as chaves do .env para os Secrets do GitHub, de onde os horarios
automaticos leem. Rode depois de conectar as contas ou de trocar uma chave
(a da Groq, por exemplo): o GitHub nao le o .env da sua maquina.

Se ainda nao houver GH_PAT, abre a pagina de criacao ja com o escopo certo e
pede para colar o token, que vai direto para o .env.

Uso:
    python -m src.push_secrets
"""
import sys
import webbrowser

from src import credentials
from src.env_file import ENV_FILE, update_env_file


def main() -> None:
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
