"""Cliente minimo para a YouTube Data API v3 (upload de Shorts).

Diferente do TikTok, o refresh_token do Google normalmente NAO rotaciona a
cada uso (fica valido ate ser revogado ou o app perder acesso), entao nao
precisamos atualizar o secret no GitHub a cada execucao.

Requisito: o app OAuth no Google Cloud precisa estar com publishing status
"In production" (nao "Testing"), senao o refresh_token expira em 7 dias.
Veja README.md para o passo a passo.
"""
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
RETRIABLE_STATUS_CODES = (500, 502, 503, 504)
MAX_UPLOAD_RETRIES = 5


def _build_client(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload_short(client_id: str, client_secret: str, refresh_token: str,
                  video_path: str, title: str, description: str,
                  category_id: str = "24", privacy_status: str = "public",
                  made_for_kids: bool = False) -> dict:
    """Envia o video como YouTube Short. Retorna o recurso 'video' criado."""
    youtube = _build_client(client_id, client_secret, refresh_token)

    # titulo tem limite de 100 caracteres na API do YouTube
    title = title[:100]
    if "#shorts" not in description.lower():
        description = f"{description}\n\n#Shorts"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
        except HttpError as exc:
            # upload resumable: erro transitorio do servidor da pra retomar do
            # ponto em que parou, sem reenviar o video inteiro
            if exc.resp.status not in RETRIABLE_STATUS_CODES or retries >= MAX_UPLOAD_RETRIES:
                raise
            retries += 1
            wait = 2 ** retries
            print(f"  [youtube] erro {exc.resp.status} no upload, retomando em {wait}s "
                  f"({retries}/{MAX_UPLOAD_RETRIES})")
            time.sleep(wait)
            continue

        if status:
            print(f"  [youtube] upload {int(status.progress() * 100)}%")

    return response
