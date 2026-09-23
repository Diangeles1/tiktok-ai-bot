"""Painel local: gera o video acompanhando cada etapa e publica com um clique.

Abre uma pagina no navegador com a geracao ao vivo (roteiro, cada imagem de
cena chegando, narracao, montagem), o video pronto para conferir e os botoes
de publicar. Nada sai para as plataformas sem voce aprovar na pagina.

Roda so na sua maquina: escuta apenas em 127.0.0.1 e le as chaves do .env,
que nunca sao enviadas para a pagina. A geracao e a publicacao rodam o mesmo
main.py do GitHub Actions, entao o video sai igual ao da publicacao automatica.

Uso:  python painel.py
      python painel.py --celular   (abre tambem para o celular no mesmo wi-fi,
                                    protegido por um codigo de 6 digitos)
"""
import argparse
import base64
import datetime
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import requests
import yaml

from src import script_gen, tiktok_api, tiktok_token
from src.github_videos import AUTO_PREFIX, append_history, fetch_github_videos
from src.env_file import read_env_file

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "output")
PAGE_PATH = os.path.join(ROOT, "web", "painel.html")
BRASILIA_UTC_OFFSET = -3

RUN_NAME_RE = re.compile(r"^[\w.-]+$")
STEP_RE = re.compile(r"^\[(\d)/\d\]")
SCENE_RE = re.compile(r"\[cena \d+/(\d+)\]")
MAX_BODY_BYTES = 64 * 1024
PLATFORMS = ("tiktok", "youtube")

# modo celular: o codigo e curto para caber na digitacao, entao a porta trava
# depois de poucos erros. Quem esta na rede nao tem tentativas infinitas.
PIN_MAX_ERROS = 8
PIN_TRAVA_SEGUNDOS = 120
COOKIE_HORAS = 12

# o painel mostra se cada chave existe, nunca o valor
CREDENTIALS = {
    "groq": ("GROQ_API_KEY",),
    "tiktok": ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"),
    "youtube": ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"),
    "github": ("GH_PAT", "GH_REPOSITORY"),
}

CONTENT_TYPES = {
    ".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".mp3": "audio/mpeg", ".json": "application/json",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_config() -> dict:
    with open(os.path.join(ROOT, os.environ.get("CONFIG_FILE") or "config.yaml"),
              encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_json(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def run_path(name: str) -> str | None:
    """Caminho da pasta de uma execucao, ou None se o nome for invalido."""
    if not RUN_NAME_RE.match(name or ""):
        return None
    path = os.path.join(OUTPUT_DIR, name)
    return path if os.path.isdir(path) else None


def run_summary(name: str) -> dict:
    path = os.path.join(OUTPUT_DIR, name)
    video = os.path.join(path, "final.mp4")
    meta_path = os.path.join(path, "metadata.json")
    return {
        "nome": name,
        "modificado": os.path.getmtime(video if os.path.exists(video) else meta_path),
        "metadata": read_json(meta_path) or {},
        "publicacao": read_json(os.path.join(path, "publicacao.json")) or {},
        "tem_video": os.path.exists(video),
        "tem_capa": os.path.exists(os.path.join(path, "thumbnail.jpg")),
        "automatico": name.startswith(AUTO_PREFIX),
    }


def list_runs() -> list[dict]:
    if not os.path.isdir(OUTPUT_DIR):
        return []
    runs = [run_summary(name) for name in os.listdir(OUTPUT_DIR)
            if RUN_NAME_RE.match(name)
            and os.path.isfile(os.path.join(OUTPUT_DIR, name, "metadata.json"))]
    return sorted(runs, key=lambda r: r["modificado"], reverse=True)


class Job:
    """Um main.py rodando em segundo plano, com o log guardado para a pagina.

    Roda como processo separado (e nao importado aqui) para um erro no meio do
    render nao derrubar o painel, e para o cancelar poder matar tudo junto."""

    def __init__(self, kind: str, run_name: str, cmd: list[str], env: dict):
        self.id = secrets.token_hex(4)
        self.kind = kind
        self.run = run_name
        self.started = time.time()
        self.ended = None
        self.status = "rodando"
        self.step = 0
        self.scene_total = 0
        self.scenes_started = 0
        self.cancelled = False
        self.lines: list[str] = []
        self.lock = threading.Lock()
        self.proc = subprocess.Popen(
            cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for raw in self.proc.stdout:
            line = raw.rstrip("\n")
            with self.lock:
                self.lines.append(line)
                step = STEP_RE.match(line)
                if step:
                    self.step = int(step.group(1))
                scene = SCENE_RE.search(line)
                if scene:
                    self.scene_total = int(scene.group(1))
                    self.scenes_started += 1
        code = self.proc.wait()
        with self.lock:
            self.ended = time.time()
            if self.cancelled:
                self.status = "cancelado"
            elif code == 0:
                self.status = "ok"
                if self.kind == "gerar":
                    self.step = 5
            else:
                self.status = "erro"

    def cancel(self) -> None:
        if self.proc.poll() is not None:
            return
        self.cancelled = True
        if os.name == "nt":
            # /T leva junto o ffmpeg que o MoviePy abriu; so matar o python
            # deixaria o render rodando sozinho
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)],
                           capture_output=True)
        else:
            self.proc.terminate()

    def ready_scenes(self) -> list[str]:
        """Imagens de cena ja terminadas. Uma imagem so conta como pronta
        quando o log passa para a proxima, senao a pagina pegaria o arquivo
        ainda sendo gravado."""
        if self.kind != "gerar":
            return []
        with self.lock:
            if self.step >= 3 or self.status == "ok":
                ready = self.scene_total
            elif self.step == 2:
                ready = max(0, self.scenes_started - 1)
            else:
                ready = 0
        scenes_dir = os.path.join(OUTPUT_DIR, self.run, "scenes")
        names = [f"scene_{i:02d}.jpg" for i in range(ready)]
        return [n for n in names if os.path.exists(os.path.join(scenes_dir, n))]

    def snapshot(self, since: int = 0) -> dict:
        scenes = self.ready_scenes()
        with self.lock:
            return {
                "id": self.id,
                "tipo": self.kind,
                "execucao": self.run,
                "status": self.status,
                "etapa": self.step,
                "cenas_total": self.scene_total,
                "cenas_prontas": scenes,
                "segundos": round((self.ended or time.time()) - self.started, 1),
                "linhas": self.lines[since:],
                "total_linhas": len(self.lines),
            }


class Busy(Exception):
    pass


class TikTokUnavailable(Exception):
    """A tela de publicar direto nao pode ser mostrada. `reason` diz a pagina
    o que oferecer no lugar (reconectar, esperar o limite, etc.)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


# erros do TikTok que pedem reconectar a conta, e nao tentar de novo
RECONNECT_CODES = {"scope_not_authorized", "access_token_invalid"}
# o TikTok pede para parar de publicar enquanto durar
BLOCKING_CODES = {"spam_risk_too_many_posts", "spam_risk_user_banned_from_posting",
                  "reached_active_user_cap"}
TITLE_MAX_UTF16 = 2200


class TikTokAccount:
    """A conta do TikTok vista pelo painel, para a tela de publicar direto.

    O TikTok exige, antes de mostrar essa tela, consultar a conta (apelido,
    opcoes de privacidade, interacoes desligadas, duracao maxima) e so deixar
    escolher o que ela permite. O access_token fica em memoria (vale 24 horas)
    e vai para o main.py na hora de publicar, para o refresh_token nao girar
    duas vezes. Nada disso chega a pagina alem do que ela exibe."""

    def __init__(self, panel: "Panel"):
        self.panel = panel
        self.lock = threading.Lock()
        self.token: str | None = None
        self.expires = 0.0

    def access_token(self) -> str:
        with self.lock:
            if self.token and time.time() < self.expires - 600:
                return self.token
            env = self.panel.env()
            if not all(env.get(k) for k in CREDENTIALS["tiktok"]):
                raise TikTokUnavailable("chaves", "Faltam as chaves do TikTok no .env.")
            try:
                data = tiktok_api.refresh_access_token(
                    env["TIKTOK_CLIENT_KEY"], env["TIKTOK_CLIENT_SECRET"],
                    env["TIKTOK_REFRESH_TOKEN"])
            except (requests.RequestException, RuntimeError) as exc:
                raise TikTokUnavailable("reconectar",
                                        f"O TikTok recusou renovar a conexao: {exc}") from exc
            tiktok_token.save_refresh_token(data.get("refresh_token", ""), env,
                                            self.panel.env_file)
            if "video.publish" not in (data.get("scope") or "").split(","):
                raise TikTokUnavailable(
                    "permissao",
                    "A conta foi conectada sem a permissao de publicar direto (video.publish).")
            self.token = data["access_token"]
            self.expires = time.time() + int(data.get("expires_in") or 86400)
            return self.token

    def creator(self) -> dict:
        token = self.access_token()
        try:
            info = tiktok_api.query_creator_info(token)
        except tiktok_api.TikTokError as exc:
            if exc.code in RECONNECT_CODES:
                with self.lock:
                    self.token = None
                raise TikTokUnavailable("permissao" if exc.code == "scope_not_authorized"
                                        else "reconectar", str(exc)) from exc
            if exc.code in BLOCKING_CODES:
                raise TikTokUnavailable("bloqueado", str(exc)) from exc
            raise TikTokUnavailable("erro", str(exc)) from exc
        except requests.RequestException as exc:
            raise TikTokUnavailable("erro", f"Nao consegui falar com o TikTok: {exc}") from exc
        return info

    def page_info(self) -> dict:
        """O que a pagina precisa para montar a tela. A foto vai embutida (a
        pagina so carrega imagem do proprio painel)."""
        info = self.creator()
        avatar = None
        url = info.get("creator_avatar_url")
        if url and url.startswith("https://"):
            try:
                resp = requests.get(url, timeout=10)
                kind = resp.headers.get("Content-Type", "").split(";")[0]
                if resp.ok and kind.startswith("image/") and len(resp.content) < 2_000_000:
                    avatar = f"data:{kind};base64,{base64.b64encode(resp.content).decode()}"
            except requests.RequestException:
                pass  # sem foto a tela continua valida: o exigido e o apelido
        return {
            "apelido": info.get("creator_nickname") or "",
            "usuario": info.get("creator_username") or "",
            "avatar": avatar,
            "privacidades": info.get("privacy_level_options") or [],
            "comentario_desligado": bool(info.get("comment_disabled")),
            "dueto_desligado": bool(info.get("duet_disabled")),
            "costura_desligada": bool(info.get("stitch_disabled")),
            "duracao_max": info.get("max_video_post_duration_sec"),
        }

    def post_choices(self, choices: dict, meta: dict) -> dict:
        """Confere de novo, com a conta consultada agora, tudo que a pagina ja
        conferiu: a regra e do TikTok e nao pode depender so do navegador."""
        info = self.creator()
        privacy = str(choices.get("privacidade") or "")
        if privacy not in (info.get("privacy_level_options") or []):
            raise ValueError("Escolha quem pode ver o video no TikTok.")
        title = str(choices.get("legenda") or "").strip()
        if not title:
            raise ValueError("A legenda do TikTok esta vazia.")
        if len(title.encode("utf-16-le")) // 2 > TITLE_MAX_UTF16:
            raise ValueError(f"A legenda do TikTok passa de {TITLE_MAX_UTF16} caracteres.")
        disclose = bool(choices.get("divulgacao"))
        own_brand = disclose and bool(choices.get("sua_marca"))
        branded = disclose and bool(choices.get("conteudo_de_marca"))
        if disclose and not (own_brand or branded):
            raise ValueError("Na divulgacao de conteudo comercial, marque 'Sua marca', "
                             "'Conteudo de marca' ou os dois.")
        if branded and privacy == "SELF_ONLY":
            raise ValueError("Conteudo de marca nao pode ser publicado como 'Somente eu'.")
        limit = info.get("max_video_post_duration_sec")
        duration = meta.get("duracao_segundos")
        if limit and duration and float(duration) > float(limit):
            raise ValueError(f"O video tem {duration} s e esta conta aceita no maximo {limit} s.")
        return {
            "mode": "direct",
            "title": title,
            "privacy_level": privacy,
            # interacao desligada no app da pessoa fica desligada aqui tambem
            "disable_comment": not choices.get("comentario") or bool(info.get("comment_disabled")),
            "disable_duet": not choices.get("dueto") or bool(info.get("duet_disabled")),
            "disable_stitch": not choices.get("costura") or bool(info.get("stitch_disabled")),
            "brand_organic_toggle": own_brand,
            "brand_content_toggle": branded,
            "is_aigc": bool(choices.get("ia", True)),
        }


class Panel:
    def __init__(self, env_file: str):
        self.env_file = env_file
        self.token = secrets.token_urlsafe(24)
        # codigo do celular: curto de proposito, quem digita esta no seu wi-fi
        self.pin = "".join(secrets.choice("0123456789") for _ in range(6))
        self.erros_pin = 0
        self.travado_ate = 0.0
        self.job: Job | None = None
        self.lock = threading.Lock()
        self.tiktok = TikTokAccount(self)
        self.fetch_lock = threading.Lock()
        self.batch: dict | None = None

    def env(self) -> dict:
        # relido a cada execucao: publicar no TikTok e os scripts de login
        # gravam chaves novas nele
        return {**os.environ, **read_env_file(self.env_file)}

    def _start(self, kind: str, run_name: str, args: list[str], extra_env: dict) -> Job:
        with self.lock:
            if self.job and self.job.status == "rodando":
                raise Busy("Ja tem uma execucao em andamento. Espere terminar ou cancele.")
            env = {**self.env(), "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
                   **extra_env}
            self.job = Job(kind, run_name, [sys.executable, "-u", "main.py", *args], env)
            return self.job

    def generate(self, topic: str) -> Job:
        name = "painel_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return self._start("gerar", name, [], {
            "DRY_RUN": "true",
            "RUN_DIR": os.path.join("output", name),
            "TEMA": topic.strip()[:300],
        })

    def _slots_futuros(self, days: int) -> list[tuple[datetime.date, int]]:
        """Os horarios dos proximos dias que ainda nao passaram.

        O TikTok Studio agenda com no minimo 20 minutos de antecedencia e no
        maximo 10 dias, entao o lote segue essa janela."""
        hours = load_config().get("posting_hours_utc", []) or [0]
        agora = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
        alvos = []
        for dia_offset in range(max(1, min(days, 10))):
            dia = datetime.date.today() + datetime.timedelta(days=dia_offset)
            for slot, hora in enumerate(hours):
                quando = datetime.datetime.combine(
                    dia, datetime.time(hour=hora % 24), tzinfo=datetime.timezone.utc)
                if quando > agora:
                    alvos.append((dia, slot))
        return alvos

    def start_batch(self, days: int) -> dict:
        """Gera de uma vez os videos dos proximos dias, um depois do outro.

        Cada um sai com o tema, o gancho e o arco daquele horario, os mesmos
        que o horario automatico usaria, e com o horario de agendamento no
        metadata para voce marcar no TikTok Studio."""
        with self.lock:
            if self.batch and self.batch.get("ativo"):
                raise Busy("Ja tem um lote em andamento.")
            if self.job and self.job.status == "rodando":
                raise Busy("Ja tem uma execucao em andamento. Espere terminar ou cancele.")
            alvos = self._slots_futuros(days)
            if not alvos:
                raise ValueError("Nenhum horario futuro nos proximos dias.")
            self.batch = {"ativo": True, "total": len(alvos), "feitos": 0, "erros": 0,
                          "cancelado": False}
        threading.Thread(target=self._run_batch, args=(alvos,), daemon=True).start()
        return dict(self.batch)

    def _run_batch(self, alvos: list[tuple[datetime.date, int]]) -> None:
        for dia, slot in alvos:
            if self.batch.get("cancelado"):
                break
            name = f"lote_{dia.isoformat()}_{slot + 1}"
            if os.path.isdir(os.path.join(OUTPUT_DIR, name)):
                self.batch["feitos"] += 1   # ja gerado antes, nao refaz
                continue
            try:
                job = self._start("gerar", name, [], {
                    "DRY_RUN": "true",
                    "RUN_DIR": os.path.join("output", name),
                    "DATA_ALVO": dia.isoformat(),
                    "SLOT_ALVO": str(slot),
                })
            except Busy:
                break
            while job.status == "rodando":
                time.sleep(2)
            if job.status == "ok":
                self.batch["feitos"] += 1
            else:
                self.batch["erros"] += 1
                if job.status == "cancelado":
                    break
        self.batch["ativo"] = False

    def publish(self, run_name: str, platforms: list[str], tiktok: dict | None = None) -> Job:
        """`tiktok` e o que a pessoa escolheu na tela do TikTok: {"modo": "app"}
        manda para a caixa de entrada do celular; {"modo": "direto", ...}
        publica no perfil com as escolhas da tela."""
        path = run_path(run_name)
        if not path or not os.path.exists(os.path.join(path, "final.mp4")):
            raise ValueError("Video nao encontrado.")
        meta = read_json(os.path.join(path, "metadata.json"))
        if meta is None:
            raise ValueError("Essa pasta nao tem metadata.json.")
        chosen = [p for p in PLATFORMS if p in platforms]
        if not chosen:
            raise ValueError("Escolha pelo menos uma plataforma.")
        extra = {}
        if "tiktok" in chosen and tiktok:
            if tiktok.get("modo") == "direto":
                try:
                    post = self.tiktok.post_choices(tiktok, meta)
                    extra["TIKTOK_ACCESS_TOKEN"] = self.tiktok.access_token()
                except TikTokUnavailable as exc:
                    raise ValueError(str(exc)) from exc
            else:
                post = {"mode": "upload"}
            extra["TIKTOK_POST"] = json.dumps(post, ensure_ascii=False)
        return self._start("publicar", run_name, [
            "--publicar", os.path.join("output", run_name), "--plataformas", ",".join(chosen),
        ], extra)

    def cancel(self) -> None:
        with self.lock:
            if self.batch:
                self.batch["cancelado"] = True
            if self.job:
                self.job.cancel()

    def fetch_auto(self) -> dict:
        # dois cliques seguidos baixariam o mesmo video duas vezes
        if not self.fetch_lock.acquire(blocking=False):
            return {"novos": 0, "erro": "Ja estou buscando, espere terminar."}
        try:
            return fetch_github_videos(self.env(), OUTPUT_DIR)
        finally:
            self.fetch_lock.release()

    def show_video(self, run_name: str) -> None:
        """Abre a pasta do video com o arquivo ja selecionado, para arrastar
        para a pagina de upload do TikTok."""
        path = run_path(run_name)
        video = path and os.path.join(path, "final.mp4")
        if not video or not os.path.exists(video):
            raise ValueError("Video nao encontrado.")
        if os.name == "nt":
            # o explorer devolve codigo 1 mesmo quando abre: nao da para conferir
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(video)}"])
        else:
            webbrowser.open(f"file://{path}")

    def mark_posted_on_site(self, run_name: str) -> None:
        path = run_path(run_name)
        if not path:
            raise ValueError("Video nao encontrado.")
        append_history(path, "tiktok", {
            "ok": True, "modo": "site",
            "quando": datetime.datetime.now().isoformat(timespec="seconds"),
        })

    def state(self) -> dict:
        cfg = load_config()
        env = self.env()
        script_cfg = cfg.get("script", {})
        hours = cfg.get("posting_hours_utc", [])
        slot = script_gen.current_slot(hours)
        count = max(1, len(hours))
        hook = script_gen.hook_of_the_slot(script_cfg.get("hooks", []), slot_index=slot,
                                           slot_count=count)
        arc = script_gen.rotate_by_slot(script_cfg.get("arcs", []), slot_index=slot,
                                        slot_count=count)
        brand = cfg.get("branding", {})
        tiktok_cfg = cfg.get("tiktok", {})
        youtube_cfg = cfg.get("youtube", {})
        credentials = {name: all(env.get(k) for k in keys) for name, keys in CREDENTIALS.items()}
        return {
            "fase": cfg.get("fase", "monetizacao"),
            "handle": brand.get("handle"),
            "handle_provisorio": brand.get("handle") in (None, "", "@canal"),
            "env_encontrado": os.path.exists(self.env_file),
            "credenciais": credentials,
            "proximo": {
                "tema": script_gen.topic_of_the_day(script_cfg.get("topics", {}),
                                                    slot_index=slot, slot_count=count,
                                                    mistura=script_cfg.get("mistura")),
                "gancho": hook["name"] if hook else None,
                "arco": arc["name"] if arc else None,
                "tipo": script_gen.categoria_do_slot(script_cfg.get("mistura"),
                                                     slot_index=slot),
                "horario_brasilia": ((hours[slot] + BRASILIA_UTC_OFFSET) % 24) if hours else None,
            },
            # o menu de temas do painel e uma lista so: os grupos servem para
            # a rotacao, nao para quem escolhe o tema na mao
            "temas": [tema for grupo in script_cfg.get("topics", {}).values()
                      for tema in grupo],
            "lote": self.batch,
            "plataformas": {
                "tiktok": {"ativo": tiktok_cfg.get("enabled", True),
                           "modo": tiktok_cfg.get("mode", "direct"),
                           "painel_direto": bool(tiktok_cfg.get("painel_direto", False)),
                           "app_aprovado": bool(tiktok_cfg.get("app_aprovado", False)),
                           "credenciais": credentials["tiktok"]},
                "youtube": {"ativo": youtube_cfg.get("enabled", True),
                            "privacidade": youtube_cfg.get("privacy_status", "public"),
                            "credenciais": credentials["youtube"]},
            },
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "PainelCanal"

    def log_message(self, fmt, *args) -> None:
        pass  # o terminal do painel fica limpo; o log que importa esta na pagina

    @property
    def panel(self) -> Panel:
        return self.server.panel

    def _host_ok(self) -> bool:
        # barra DNS rebinding: um site externo apontando o proprio dominio para
        # 127.0.0.1 (ou para o IP da maquina na rede) chegaria aqui com outro Host
        port = self.server.server_address[1]
        host = self.headers.get("Host", "")
        nome = host.rsplit(":", 1)[0].strip("[]") if host.endswith(f":{port}") else ""
        return nome in self.server.hosts_ok

    def _tem_acesso(self) -> bool:
        """No modo celular, cada pedido precisa provar que veio do painel."""
        if not self.server.celular:
            return True
        token = self.panel.token
        if secrets.compare_digest(self.headers.get("X-Painel-Token", ""), token):
            return True
        for pedaco in self.headers.get("Cookie", "").split(";"):
            nome, _, valor = pedaco.strip().partition("=")
            if nome == "painel" and secrets.compare_digest(valor, token):
                return True
        return False

    def _pin_ok(self, digitado: str) -> bool:
        """Confere o codigo e trava a porta depois de uma sequencia de erros."""
        with self.panel.lock:
            if time.time() < self.panel.travado_ate:
                return False
            if digitado and secrets.compare_digest(digitado, self.panel.pin):
                self.panel.erros_pin = 0
                return True
            if digitado:
                self.panel.erros_pin += 1
                if self.panel.erros_pin >= PIN_MAX_ERROS:
                    self.panel.erros_pin = 0
                    self.panel.travado_ate = time.time() + PIN_TRAVA_SEGUNDOS
                    print(f"AVISO: {PIN_MAX_ERROS} codigos errados. "
                          f"Painel travado por {PIN_TRAVA_SEGUNDOS}s.")
            return False

    def _send_login(self, errado: bool = False) -> None:
        espera = int(max(0, self.panel.travado_ate - time.time()))
        if espera:
            recado = f"Muitas tentativas. Espere {espera} segundos."
        elif errado:
            recado = "Codigo errado."
        else:
            recado = "O codigo aparece na janela do painel, no PC."
        body = PAGE_LOGIN.replace("{{RECADO}}", recado).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_page(self) -> None:
        with open(PAGE_PATH, encoding="utf-8") as f:
            body = f.read().replace("{{TOKEN}}", self.panel.token).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.server.celular:
            # o player de video pede /arquivos/ direto, sem passar pelo codigo
            # da pagina: o cookie e o que autoriza esses pedidos
            self.send_header("Set-Cookie",
                             f"painel={self.panel.token}; Path=/; HttpOnly; "
                             f"SameSite=Lax; Max-Age={COOKIE_HORAS * 3600}")
        # a pagina tem o botao de publicar: nenhum outro site pode embuti-la
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "media-src 'self'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, run_name: str, rel: str) -> None:
        base = run_path(run_name)
        if not base:
            return self._send_json({"erro": "nao encontrado"}, 404)
        base = os.path.realpath(base)
        target = os.path.realpath(os.path.join(base, rel))
        try:
            inside = os.path.commonpath([base, target]) == base
        except ValueError:  # outro disco no Windows
            inside = False
        if not inside or not os.path.isfile(target):
            return self._send_json({"erro": "nao encontrado"}, 404)

        size = os.path.getsize(target)
        start, end = 0, size - 1
        status = 200
        # o player de video pede o arquivo em pedacos (Range) para poder pular
        # para qualquer ponto; sem isso a barra de tempo nao funciona
        match = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        if match and (match.group(1) or match.group(2)):
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
            else:
                start = max(0, size - int(match.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            status = 206

        ext = os.path.splitext(target)[1].lower()
        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(target, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # o navegador cancela pedacos de video o tempo todo

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._send_json({"erro": "host nao permitido"}, 403)
        url = urlparse(self.path)
        if url.path == "/":
            if self._tem_acesso():
                return self._send_page()
            digitado = parse_qs(url.query).get("c", [""])[0].strip()
            if self._pin_ok(digitado):
                return self._send_page()
            return self._send_login(errado=bool(digitado))
        if not self._tem_acesso():
            return self._send_json({"erro": "sem acesso, abra o painel de novo"}, 403)
        if url.path == "/api/estado":
            return self._send_json(self.panel.state())
        if url.path == "/api/execucoes":
            return self._send_json(list_runs())
        if url.path == "/api/job":
            job = self.panel.job
            try:
                since = int(parse_qs(url.query).get("desde", ["0"])[0])
            except ValueError:
                since = 0
            return self._send_json({"job": job.snapshot(since) if job else None})
        if url.path.startswith("/arquivos/"):
            parts = unquote(url.path[len("/arquivos/"):]).split("/", 1)
            if len(parts) == 2:
                return self._send_file(parts[0], parts[1])
        self._send_json({"erro": "nao encontrado"}, 404)

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._send_json({"erro": "host nao permitido"}, 403)
        # sem o token, que so a propria pagina conhece, outro site aberto no
        # navegador poderia mandar publicar
        if not secrets.compare_digest(self.headers.get("X-Painel-Token", ""), self.panel.token):
            return self._send_json({"erro": "token invalido, recarregue a pagina"}, 403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY_BYTES:
            return self._send_json({"erro": "pedido grande demais"}, 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send_json({"erro": "JSON invalido"}, 400)
        if not isinstance(body, dict):
            return self._send_json({"erro": "JSON invalido"}, 400)

        path = urlparse(self.path).path
        try:
            if path == "/api/gerar":
                job = self.panel.generate(str(body.get("tema") or ""))
                return self._send_json({"job": job.snapshot()})
            if path == "/api/lote":
                try:
                    dias = int(body.get("dias") or 3)
                except (TypeError, ValueError):
                    raise ValueError("dias precisa ser um numero.")
                return self._send_json({"lote": self.panel.start_batch(dias)})
            if path == "/api/publicar":
                platforms = body.get("plataformas") or []
                if not isinstance(platforms, list):
                    raise ValueError("plataformas precisa ser uma lista.")
                tiktok = body.get("tiktok")
                if tiktok is not None and not isinstance(tiktok, dict):
                    raise ValueError("tiktok precisa ser um objeto.")
                job = self.panel.publish(str(body.get("execucao") or ""),
                                         [str(p) for p in platforms], tiktok)
                return self._send_json({"job": job.snapshot()})
            if path == "/api/tiktok/conta":
                # POST e nao GET: consultar renova o token, e so a pagina do
                # painel (que tem o token dela) pode pedir isso
                try:
                    return self._send_json({"ok": True, **self.panel.tiktok.page_info()})
                except TikTokUnavailable as exc:
                    return self._send_json({"ok": False, "motivo": exc.reason,
                                            "mensagem": str(exc)})
            if path == "/api/cancelar":
                self.panel.cancel()
                return self._send_json({"ok": True})
            if path == "/api/github/buscar":
                return self._send_json(self.panel.fetch_auto())
            if path == "/api/mostrar-video":
                self.panel.show_video(str(body.get("execucao") or ""))
                return self._send_json({"ok": True})
            if path == "/api/tiktok/postado-no-site":
                self.panel.mark_posted_on_site(str(body.get("execucao") or ""))
                return self._send_json({"ok": True})
        except Busy as exc:
            return self._send_json({"erro": str(exc)}, 409)
        except ValueError as exc:
            return self._send_json({"erro": str(exc)}, 400)
        self._send_json({"erro": "nao encontrado"}, 404)


PAGE_LOGIN = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel do canal</title>
<style>
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: #f5f2ec; color: #1f1b16;
         font: 16px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }
  form { background: #fff; padding: 28px 24px; border-radius: 14px; width: 260px;
         box-shadow: 0 2px 16px rgba(0,0,0,.08); text-align: center; }
  h1 { font-size: 18px; margin: 0 0 6px; }
  p { color: #6d655a; font-size: 14px; margin: 0 0 18px; }
  input { width: 100%; box-sizing: border-box; padding: 12px; font-size: 24px;
          text-align: center; letter-spacing: 6px; border: 1px solid #e6dfd3;
          border-radius: 10px; background: #faf7f2; color: inherit; }
  button { width: 100%; margin-top: 12px; padding: 12px; font-size: 16px;
           border: 0; border-radius: 10px; background: #a8731f; color: #fff; }
  @media (prefers-color-scheme: dark) {
    body { background: #14120f; color: #f2ece2; }
    form { background: #1d1a15; box-shadow: none; }
    p { color: #a79d8e; }
    input { background: #14120f; border-color: #3a342b; }
  }
</style></head>
<body><form method="get" action="/">
  <h1>Painel do canal</h1>
  <p>{{RECADO}}</p>
  <input name="c" inputmode="numeric" pattern="[0-9]*" maxlength="6"
         autocomplete="off" autofocus placeholder="000000">
  <button type="submit">Entrar</button>
</form></body></html>
"""


def ip_da_rede() -> str | None:
    """IP desta maquina no wi-fi, que e o endereco que o celular precisa usar."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 53))   # UDP: escolhe a placa de rede, nao envia nada
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def porta_ocupada(porta: int) -> bool:
    """Alguem ja atende nessa porta na propria maquina?

    No Windows, ligar em 0.0.0.0 nao esbarra em quem ligou so em 127.0.0.1: os
    dois sobem calados e o celular acabaria falando com outro painel.
    """
    try:
        with socket.create_connection(("127.0.0.1", porta), 0.3):
            return True
    except OSError:
        return False


def mostra_qr(url: str) -> None:
    """QR code no terminal: a camera do celular abre o painel sem digitacao."""
    try:
        import qrcode
    except ImportError:
        print("Sem QR code aqui (pip install qrcode). Digite o endereco no celular.")
        return
    codigo = qrcode.QRCode(border=1)
    codigo.add_data(url)
    codigo.print_ascii(invert=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    celular = False
    hosts_ok = frozenset({"127.0.0.1", "localhost"})
    # no Windows, reusar o endereco deixa dois processos ouvindo a mesma porta
    # em silencio, e a pagina falaria com o painel errado
    allow_reuse_address = os.name != "nt"


def main() -> None:
    parser = argparse.ArgumentParser(description="Painel local do canal.")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--env", default=os.path.join(ROOT, ".env"),
                        help="arquivo de chaves (padrao: .env do projeto)")
    parser.add_argument("--sem-navegador", action="store_true",
                        help="nao abre o navegador sozinho")
    parser.add_argument("--celular", action="store_true",
                        help="deixa o painel acessivel do celular no mesmo wi-fi")
    parser.add_argument("--config", default=os.environ.get("CONFIG_FILE") or "config.yaml",
                        help="config do canal (padrao: config.yaml)")
    args = parser.parse_args()
    # o main.py roda como processo separado e le esta variavel
    os.environ["CONFIG_FILE"] = args.config

    ip = ip_da_rede() if args.celular else None
    if args.celular and not ip:
        sys.exit("Nao achei o IP desta maquina na rede. Conecte o PC ao wi-fi e tente de novo.")

    server = None
    for port in range(args.porta, args.porta + 10):
        if args.celular and porta_ocupada(port):
            continue
        try:
            server = Server(("0.0.0.0" if args.celular else "127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        sys.exit(f"Nenhuma porta livre entre {args.porta} e {args.porta + 9}.")

    server.panel = Panel(os.path.abspath(args.env))
    porta = server.server_address[1]
    url = f"http://127.0.0.1:{porta}/"
    if args.celular:
        server.celular = True
        server.hosts_ok = frozenset({"127.0.0.1", "localhost", ip})
        url = f"http://127.0.0.1:{porta}/?c={server.panel.pin}"
        celular_url = f"http://{ip}:{porta}/?c={server.panel.pin}"
        print("No celular, aponte a camera para este QR code:\n")
        mostra_qr(celular_url)
        print(f"Ou digite no navegador do celular:  {ip}:{porta}")
        print(f"Codigo: {server.panel.pin}")
        print("Precisa estar no mesmo wi-fi que este PC.")
        print("Se o celular nao abrir, libere a porta no firewall do Windows.\n")
    print(f"Painel aberto em {url}")
    print("Deixe esta janela aberta enquanto usa o painel. Ctrl+C fecha.")
    if not os.path.exists(args.env):
        print(f"AVISO: {args.env} nao encontrado. Sem chaves, o painel nao gera nem publica.")
    if not args.sem_navegador:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # fechar o painel no meio de um render nao pode deixar o processo solto
        server.panel.cancel()
        server.server_close()
        print("Painel fechado.")


if __name__ == "__main__":
    main()
