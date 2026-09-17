"""Cliente minimo para a TikTok Content Posting API.

Fluxo:
 1. refresh_access_token() troca o refresh_token por um access_token novo
    (o refresh_token pode rotacionar -> quem chama deve persistir o novo valor).
 2. query_creator_info() consulta as opcoes de privacidade permitidas para o criador.
 3. init_video_post() inicia o post e devolve (publish_id, upload_url).
 4. upload_video() envia os bytes do video para upload_url.
 5. poll_status() consulta o status ate finalizar.

Apps NAO auditados só podem publicar com privacy_level="SELF_ONLY" (visivel
apenas para o proprio criador, como um rascunho). Depois que o app passar
pela auditoria da TikTok, "PUBLIC_TO_EVERYONE" passa a ficar disponivel.
"""
import os
import time
from typing import Callable

import requests

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def refresh_access_token(client_key: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Falha ao renovar token TikTok: {data}")
    return data


def query_creator_info(access_token: str) -> dict:
    resp = requests.post(
        CREATOR_INFO_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def init_video_post(access_token: str, video_size: int, title: str, privacy_level: str = "SELF_ONLY") -> dict:
    body = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1,
        },
    }
    resp = requests.post(
        INIT_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"Falha ao iniciar post no TikTok: {data}")
    return data["data"]


def upload_video(upload_url: str, video_path: str) -> None:
    video_size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    resp = requests.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        },
        data=video_bytes,
        timeout=300,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Falha no upload do video: {resp.status_code} {resp.text}")


def poll_status(access_token: str, publish_id: str, timeout_s: int = 180) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.post(
            STATUS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data.get("status")
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            return data
        time.sleep(5)
    raise TimeoutError(f"Status do post nao finalizou a tempo (publish_id={publish_id})")


def post_video(client_key: str, client_secret: str, refresh_token: str,
                video_path: str, title: str, privacy_level: str = "SELF_ONLY",
                on_token_refreshed: Callable[[str], None] | None = None) -> dict:
    """Fluxo completo. Retorna dict com o refresh_token atualizado e o status final.

    `on_token_refreshed` e chamado assim que o token novo chega, antes do upload:
    o TikTok invalida o refresh_token antigo na renovacao, entao se o envio
    falhasse antes de persistirmos o valor novo, o bot ficaria travado com um
    token morto e exigiria refazer o OAuth na mao."""
    token_data = refresh_access_token(client_key, client_secret, refresh_token)
    access_token = token_data["access_token"]
    new_refresh_token = token_data.get("refresh_token", refresh_token)
    if on_token_refreshed:
        on_token_refreshed(new_refresh_token)

    video_size = os.path.getsize(video_path)
    init_data = init_video_post(access_token, video_size, title, privacy_level)
    upload_video(init_data["upload_url"], video_path)
    status = poll_status(access_token, init_data["publish_id"])

    if status.get("status") == "FAILED":
        raise RuntimeError(f"TikTok recusou a publicacao: {status}")

    return {
        "new_refresh_token": new_refresh_token,
        "publish_id": init_data["publish_id"],
        "status": status,
    }
