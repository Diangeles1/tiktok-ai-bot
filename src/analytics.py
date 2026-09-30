"""Coleta de desempenho dos videos publicados (YouTube Analytics API v2).

POR QUE ISTO EXISTE: o canal publicava sozinho e nao media nada. Sem view,
sem retencao e sem taxa de conclusao, qualquer mudanca de roteiro e palpite
com cara de decisao, e palpite acumulado desfaz a identidade do canal sem
ninguem ter decidido nada.

O que ele junta:

    publicacao.json  ->  id do video no YouTube
    metadata.json    ->  gancho, arco, fase, tema, narracao
    Analytics API    ->  views, duracao media assistida, % assistida

E essa juncao que transforma numero em evidencia: sem ligar a metrica ao
ROTEIRO que a produziu, saber que um video foi bem nao ensina nada.

ESCOPO. A Analytics API precisa de "yt-analytics.readonly", que o token atual
NAO tem: o app foi autorizado so para upload. Enquanto a autorizacao nao for
refeita, a chamada volta 403 e este modulo diz isso em vez de falhar feio.
O escopo de upload continua intocado de proposito, para a publicacao, que
hoje funciona, nao correr risco.
"""
import glob
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ESCOPO_LEITURA = "https://www.googleapis.com/auth/yt-analytics.readonly"
TOKEN_URI = "https://oauth2.googleapis.com/token"

# As quatro que respondem as perguntas da otimizacao: quantos vieram, quanto
# ficaram, que fracao do video assistiram, e quanto tempo total gerou.
METRICAS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage"


class SemPermissao(RuntimeError):
    """O token nao tem o escopo de leitura de Analytics."""


def _cliente(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[ESCOPO_LEITURA],
    )
    try:
        creds.refresh(Request())
    except Exception as erro:
        raise SemPermissao(
            "nao consegui renovar o token para ler Analytics. Rode de novo o "
            "setup do OAuth para conceder o escopo yt-analytics.readonly: "
            "python -m src.youtube_oauth_setup"
        ) from erro
    return build("youtubeAnalytics", "v2", credentials=creds)


def metricas_do_video(cliente, video_id: str, desde: str = "2020-01-01",
                      ate: str | None = None) -> dict:
    """Numeros acumulados de um video, do lancamento ate hoje."""
    from datetime import date

    resposta = cliente.reports().query(
        ids="channel==MINE",
        startDate=desde,
        endDate=ate or date.today().isoformat(),
        metrics=METRICAS,
        filters=f"video=={video_id}",
    ).execute()

    linhas = resposta.get("rows") or []
    if not linhas:
        # video novo demais: o Analytics leva algumas horas para ter dado
        return {"video_id": video_id, "sem_dados": True}

    nomes = [c["name"] for c in resposta["columnHeaders"]]
    dados = dict(zip(nomes, linhas[0]))
    dados["video_id"] = video_id
    return dados


def videos_publicados(raiz: str = "output") -> list[dict]:
    """Todos os videos que tem id do YouTube, com a pasta e o roteiro."""
    achados = []
    for pub in sorted(glob.glob(os.path.join(raiz, "*", "publicacao.json"))):
        pasta = os.path.dirname(pub)
        try:
            with open(pub, encoding="utf-8") as f:
                registro = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        for envio in registro.get("youtube") or []:
            if not envio.get("ok") or not envio.get("id"):
                continue
            meta = {}
            caminho_meta = os.path.join(pasta, "metadata.json")
            if os.path.exists(caminho_meta):
                with open(caminho_meta, encoding="utf-8") as f:
                    meta = json.load(f)
            achados.append({
                "pasta": pasta,
                "video_id": envio["id"],
                "url": envio.get("url", ""),
                "publicado_em": envio.get("quando", ""),
                "metadata": meta,
            })
    return achados


def coletar(client_id: str, client_secret: str, refresh_token: str,
            raiz: str = "output") -> list[dict]:
    """Puxa a metrica de cada video publicado e grava metricas.json na pasta.

    Grava ao lado do metadata para a metrica viajar junto do roteiro que a
    produziu: separar os dois seria perder a unica coisa que interessa.
    """
    cliente = _cliente(client_id, client_secret, refresh_token)
    saida = []
    for video in videos_publicados(raiz):
        try:
            numeros = metricas_do_video(cliente, video["video_id"])
        except HttpError as erro:
            if erro.resp.status == 403:
                raise SemPermissao(
                    "a API respondeu 403. O token provavelmente nao tem o "
                    "escopo yt-analytics.readonly. Refaca o OAuth."
                ) from erro
            raise

        registro = {
            "video_id": video["video_id"],
            "url": video["url"],
            "publicado_em": video["publicado_em"],
            "metricas": numeros,
            # o pedaco do roteiro que interessa para comparar videos entre si
            "roteiro": {
                k: video["metadata"].get(k)
                for k in ("gancho", "arco", "fase", "tema",
                          "primeira_frase", "duracao_segundos")
            },
        }
        caminho = os.path.join(video["pasta"], "metricas.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=2)
        saida.append(registro)
    return saida
