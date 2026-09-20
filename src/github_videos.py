"""Videos do horario automatico e historico de publicacao.

O GitHub Actions gera e publica no YouTube; o artifact de cada execucao leva
o video, a capa, o metadata.json e o publicacao.json. O painel e o robo do
TikTok baixam esses artifacts para output/auto_<execucao> e anotam no
publicacao.json o que sai de cada lugar."""
import datetime
import json
import os
import shutil
import time
import zipfile

import requests

# pasta dos videos baixados do horario automatico (artifact do GitHub Actions)
AUTO_PREFIX = "auto_"
AUTO_FILES = ("final.mp4", "thumbnail.jpg", "metadata.json", "publicacao.json")
AUTO_MAX_BYTES = 300 * 1024 * 1024
GITHUB_API = "https://api.github.com"


def read_json(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def append_history(path: str, platform: str, outcome: dict) -> None:
    """Acrescenta uma tentativa ao publicacao.json, no mesmo formato do main.py."""
    history_path = os.path.join(path, "publicacao.json")
    history = read_json(history_path) or {}
    history.setdefault(platform, []).append(outcome)
    tmp = history_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp, history_path)


def _iso_epoch(value: str | None) -> float | None:
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def fetch_github_videos(env: dict, output_dir: str, limit: int = 12) -> dict:
    """Baixa para output/auto_<execucao> os videos que o horario automatico
    gerou no GitHub Actions e ainda nao estao aqui.

    Le so a lista de artifacts e o zip de cada um; do zip extrai apenas os
    arquivos esperados, pelo nome, e nunca um caminho vindo de dentro dele."""
    token, repo = env.get("GH_PAT"), env.get("GH_REPOSITORY")
    if not token or not repo:
        return {"novos": 0, "erro": "Faltam GH_PAT e GH_REPOSITORY no .env."}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        resp = requests.get(f"{GITHUB_API}/repos/{repo}/actions/artifacts",
                            headers=headers, params={"per_page": 50}, timeout=30)
        resp.raise_for_status()
        artifacts = resp.json().get("artifacts", [])
    except (requests.RequestException, ValueError) as exc:
        return {"novos": 0, "erro": f"Nao consegui falar com o GitHub: {exc}"}

    wanted = [a for a in artifacts
              if a.get("name", "").startswith("video-") and not a.get("expired")
              and a.get("size_in_bytes", 0) < AUTO_MAX_BYTES][:limit]
    new, errors = 0, []
    os.makedirs(output_dir, exist_ok=True)
    for art in wanted:
        run_id = str((art.get("workflow_run") or {}).get("id") or art["id"])
        dest = os.path.join(output_dir, f"{AUTO_PREFIX}{run_id}")
        if os.path.isdir(dest):
            continue
        # o "~" fica fora do RUN_NAME_RE: um download pela metade nunca aparece
        # na lista de videos
        tmp_zip = os.path.join(output_dir, f"~{AUTO_PREFIX}{run_id}.zip")
        partial = os.path.join(output_dir, f"~{AUTO_PREFIX}{run_id}")
        try:
            # o GitHub redireciona para um link temporario de outro dominio, e o
            # requests nao leva o token junto nesse salto
            with requests.get(f"{GITHUB_API}/repos/{repo}/actions/artifacts/{art['id']}/zip",
                              headers=headers, timeout=120, stream=True) as dl:
                dl.raise_for_status()
                with open(tmp_zip, "wb") as f:
                    for chunk in dl.iter_content(256 * 1024):
                        f.write(chunk)
            with zipfile.ZipFile(tmp_zip) as zf:
                by_name = {}
                for info in zf.infolist():
                    base = os.path.basename(info.filename)
                    if base in AUTO_FILES and base not in by_name:
                        by_name[base] = info
                if "final.mp4" not in by_name or "metadata.json" not in by_name:
                    continue  # execucao que falhou antes de terminar o video
                shutil.rmtree(partial, ignore_errors=True)
                os.makedirs(partial)
                # a lista ordena pela data do arquivo: sem isso todo video
                # baixado pareceria gerado agora
                created = _iso_epoch(art.get("created_at")) or time.time()
                for base, info in by_name.items():
                    target = os.path.join(partial, base)
                    with zf.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    os.utime(target, (created, created))
                os.replace(partial, dest)
                new += 1
        except (requests.RequestException, zipfile.BadZipFile, OSError) as exc:
            errors.append(f"{art.get('name')}: {exc}")
        finally:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
            shutil.rmtree(partial, ignore_errors=True)
    result = {"novos": new}
    if errors:
        result["erro"] = "Alguns videos nao baixaram: " + "; ".join(errors[:3])
    return result
