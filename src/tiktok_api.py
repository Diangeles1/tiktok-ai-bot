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
# Modo Upload: o video vai para a caixa de entrada do app e o criador finaliza
# a postagem no TikTok, escolhendo legenda e privacidade la. Como quem publica
# e a pessoa e nao o app, a trava de "app nao auditado so posta privado" (que a
# documentacao descreve para o Direct Post) nao se aplica ao que ela publicar.
# Limite documentado: no maximo 5 envios pendentes em 24 horas.
INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"

# campos de post_info que a tela de publicar do painel preenche, alem de titulo
# e privacidade. Nomes da referencia do Direct Post.
POST_OPTIONS = ("disable_comment", "disable_duet", "disable_stitch",
                "brand_content_toggle", "brand_organic_toggle", "is_aigc")

# o TikTok responde com um codigo em ingles; estes sao os que a pessoa consegue
# resolver sozinha, com o que fazer
ERROR_MESSAGES = {
    "unaudited_client_can_only_post_to_private_accounts":
        "Enquanto o TikTok nao aprovar o app, publicar direto so funciona com a conta "
        "em modo privado e como 'Somente eu'. Para sair publico agora, mande para o app "
        "do celular.",
    "privacy_level_option_mismatch":
        "Essa opcao de quem pode ver nao vale para esta conta. Atualize os dados da conta "
        "no painel e escolha de novo.",
    "spam_risk_too_many_posts":
        "O TikTok limitou as publicacoes desta conta por hoje. Tente mais tarde.",
    "spam_risk_too_many_pending_share":
        "Ha envios demais esperando na caixa de entrada do app (limite de 5 em 24 horas). "
        "Finalize ou descarte os rascunhos no celular.",
    "spam_risk_user_banned_from_posting":
        "O TikTok bloqueou publicacoes desta conta no momento.",
    "reached_active_user_cap":
        "O app atingiu o limite diario de contas do TikTok. Tente amanha.",
    "scope_not_authorized":
        "A conexao com o TikTok nao tem permissao para isso. Reconecte a conta "
        "(python -m src.oauth_setup --sem-terminal).",
    "access_token_invalid":
        "A conexao com o TikTok expirou. Reconecte a conta "
        "(python -m src.oauth_setup --sem-terminal).",
    "rate_limit_exceeded":
        "Muitos pedidos ao TikTok em pouco tempo. Espere um minuto e tente de novo.",
}


class TikTokError(RuntimeError):
    """Erro devolvido pela API, com o codigo original para quem precisa decidir
    o que fazer (o painel, por exemplo, troca a tela quando falta permissao)."""

    def __init__(self, code: str, message: str, action: str):
        self.code = code or "erro_desconhecido"
        detail = ERROR_MESSAGES.get(self.code) or message or "sem detalhe"
        super().__init__(f"{action}: {detail} [{self.code}]")


def _read(resp: requests.Response, action: str) -> dict:
    """Le a resposta checando o erro do TikTok antes do status HTTP: nos erros
    o TikTok responde 4xx com o codigo no corpo, e o raise_for_status sozinho
    jogaria fora justamente o que diz o que fazer."""
    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise TikTokError("resposta_invalida", resp.text[:200], action)
    error = data.get("error") or {}
    if isinstance(error, dict) and error.get("code") not in (None, "ok"):
        raise TikTokError(error.get("code"), error.get("message", ""), action)
    resp.raise_for_status()
    return data


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
    """Conta que vai receber o post: apelido, foto, opcoes de privacidade
    permitidas, interacoes desligadas no app e duracao maxima. O TikTok exige
    consultar isso antes de mostrar a tela de publicar. Exige video.publish."""
    resp = requests.post(
        CREATOR_INFO_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        timeout=30,
    )
    return _read(resp, "Falha ao consultar a conta do TikTok")["data"]


def init_video_post(access_token: str, video_size: int, title: str, privacy_level: str = "SELF_ONLY",
                    options: dict | None = None) -> dict:
    post_info = {
        "title": title,
        "privacy_level": privacy_level,
        "disable_duet": False,
        "disable_comment": False,
        "disable_stitch": False,
    }
    post_info.update({k: bool(v) for k, v in (options or {}).items() if k in POST_OPTIONS})
    body = {
        "post_info": post_info,
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
    return _read(resp, "Falha ao iniciar post no TikTok")["data"]


def init_inbox_upload(access_token: str, video_size: int) -> dict:
    """Inicia o envio para a caixa de entrada. Nao existe post_info aqui: legenda
    e privacidade sao escolhidas pelo criador no app."""
    body = {"source_info": {
        "source": "FILE_UPLOAD",
        "video_size": video_size,
        "chunk_size": video_size,
        "total_chunk_count": 1,
    }}
    resp = requests.post(
        INBOX_INIT_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json=body,
        timeout=30,
    )
    return _read(resp, "Falha ao enviar para a caixa de entrada do TikTok")["data"]


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


def poll_status(access_token: str, publish_id: str, timeout_s: int = 180,
                done: tuple[str, ...] = ("PUBLISH_COMPLETE",)) -> dict:
    """Espera o post chegar a um estado final. FAILED sempre encerra.

    No modo Upload o estado final do lado do bot e SEND_TO_USER_INBOX: o
    PUBLISH_COMPLETE so aparece quando a pessoa posta no app, possivelmente
    horas depois, e esperar por ele estouraria o tempo num envio que deu certo."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.post(
            STATUS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
            timeout=30,
        )
        data = _read(resp, "Falha ao consultar o status do post")["data"]
        status = data.get("status")
        if status == "FAILED" or status in done:
            return data
        time.sleep(5)
    raise TimeoutError(f"Status do post nao finalizou a tempo (publish_id={publish_id})")


def post_video(client_key: str, client_secret: str, refresh_token: str,
                video_path: str, title: str, privacy_level: str = "SELF_ONLY",
                on_token_refreshed: Callable[[str], None] | None = None,
                mode: str = "direct", options: dict | None = None,
                access_token: str | None = None) -> dict:
    """Fluxo completo. Retorna dict com o refresh_token atualizado e o status final.

    `on_token_refreshed` e chamado assim que o token novo chega, antes do upload:
    o TikTok invalida o refresh_token antigo na renovacao, entao se o envio
    falhasse antes de persistirmos o valor novo, o bot ficaria travado com um
    token morto e exigiria refazer o OAuth na mao.

    `access_token` pula a renovacao: o painel ja renovou para consultar a conta
    antes de mostrar a tela de publicar, e o token vale 24 horas.
    `options` sao os campos de POST_OPTIONS escolhidos nessa tela."""
    # valida antes de qualquer rede: renovar o token gira o refresh_token (o
    # TikTok invalida o antigo), entao um erro de digitacao no config nao pode
    # ser descoberto so depois disso
    if mode not in ("upload", "direct"):
        raise ValueError(f"tiktok.mode desconhecido: {mode!r} (use 'upload' ou 'direct')")

    new_refresh_token = refresh_token
    if not access_token:
        token_data = refresh_access_token(client_key, client_secret, refresh_token)
        access_token = token_data["access_token"]
        new_refresh_token = token_data.get("refresh_token", refresh_token)
        if on_token_refreshed:
            on_token_refreshed(new_refresh_token)

    video_size = os.path.getsize(video_path)
    if mode == "upload":
        init_data = init_inbox_upload(access_token, video_size)
        done = ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE")
    else:
        init_data = init_video_post(access_token, video_size, title, privacy_level, options)
        done = ("PUBLISH_COMPLETE",)
    upload_video(init_data["upload_url"], video_path)
    status = poll_status(access_token, init_data["publish_id"], done=done)

    if status.get("status") == "FAILED":
        raise RuntimeError(f"TikTok recusou a publicacao: {status}")

    return {
        "new_refresh_token": new_refresh_token,
        "publish_id": init_data["publish_id"],
        "status": status,
    }
