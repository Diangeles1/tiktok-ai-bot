"""Atualiza um Secret do repositorio GitHub via API (usado para persistir o
TIKTOK_REFRESH_TOKEN, que o TikTok pode rotacionar a cada renovacao).

Requer um Personal Access Token classico com escopo "repo" na variavel GH_PAT,
e o nome do repo no formato "usuario/repo" em GH_REPOSITORY.
"""
import base64

import requests
from nacl import encoding, public


def _encrypt(public_key_b64: str, secret_value: str) -> str:
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_repo_secret(gh_pat: str, repo: str, secret_name: str, secret_value: str) -> None:
    headers = {
        "Authorization": f"Bearer {gh_pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers, timeout=30,
    )
    key_resp.raise_for_status()
    key_data = key_resp.json()

    encrypted_value = _encrypt(key_data["key"], secret_value)

    put_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_data["key_id"]},
        timeout=30,
    )
    if put_resp.status_code not in (201, 204):
        raise RuntimeError(f"Falha ao atualizar secret {secret_name}: {put_resp.status_code} {put_resp.text}")
