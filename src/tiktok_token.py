"""Guarda o refresh_token do TikTok quando a renovacao devolve um novo.

Usado pelo main.py (Actions e linha de comando) e pelo painel, que renova o
token para consultar a conta antes de mostrar a tela de publicar."""
import os
from collections.abc import Mapping

from src import github_secrets
from src.env_file import update_env_file


def save_refresh_token(new_token: str, env: Mapping[str, str], env_file: str) -> None:
    """`env` e de onde vem o token atual, o GH_PAT e o GH_REPOSITORY: o
    os.environ no main.py, o .env relido no painel."""
    # o TikTok pode devolver o mesmo token na renovacao: nada a salvar
    if not new_token or new_token == env.get("TIKTOK_REFRESH_TOKEN"):
        return
    saved = False
    # rodando na maquina (painel ou linha de comando) o token vem do .env, e sem
    # atualizar o arquivo a proxima publicacao local usaria o valor ja invalido
    if os.path.exists(env_file):
        update_env_file(env_file, "TIKTOK_REFRESH_TOKEN", new_token)
        print("  [tiktok] TIKTOK_REFRESH_TOKEN atualizado no .env.")
        saved = True
    gh_pat = env.get("GH_PAT")
    gh_repo = env.get("GH_REPOSITORY")
    if gh_pat and gh_repo:
        try:
            github_secrets.update_repo_secret(gh_pat, gh_repo, "TIKTOK_REFRESH_TOKEN", new_token)
            print("  [tiktok] TIKTOK_REFRESH_TOKEN atualizado no GitHub.")
            saved = True
        except Exception as exc:
            # no Actions o GitHub e o unico lugar do token: la a falha tem que
            # parar tudo. Na maquina o .env ja guardou, entao so avisa
            if not saved:
                raise
            print(f"  [tiktok] AVISO: token salvo no .env, mas nao no GitHub ({exc}). "
                  f"A publicacao automatica vai continuar com o token antigo.")
    if not saved:
        print("  [tiktok] AVISO: GH_PAT/GH_REPOSITORY nao configurados. O novo refresh_token "
              "NAO foi salvo e a proxima execucao vai falhar. Configure esses secrets.")
