"""Leitura e escrita do .env, o arquivo de chaves desta maquina.

Usado pelo painel, pela renovacao do token do TikTok e pelos scripts de login,
que gravam as chaves aqui direto: nenhum token precisa passar pela tela, pela
area de transferencia ou pelo chat."""
import os
import re

ENV_FILE = ".env"


def read_env_file(path: str = ENV_FILE) -> dict:
    """Le as linhas CHAVE=valor, ignorando comentarios e linhas vazias."""
    values = {}
    if not os.path.exists(path):
        return values
    # utf-8-sig: o PowerShell grava o arquivo com BOM, que grudaria na 1a chave
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def update_env_file(path: str, key: str, value: str) -> None:
    """Troca o valor de uma chave (ou acrescenta, se nao existir) sem mexer no
    resto do arquivo, inclusive na quebra de linha do Windows."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            lines = f.read().splitlines(keepends=True)
    pattern = re.compile(rf"^(﻿)?\s*{re.escape(key)}\s*=")
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            ending = line[len(line.rstrip("\r\n")):]
            lines[i] = f"{match.group(1) or ''}{key}={value}{ending}"
            break
    else:
        newline = "\r\n" if any(line.endswith("\r\n") for line in lines) or (
            not lines and os.name == "nt") else "\n"
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += newline
        lines.append(f"{key}={value}{newline}")
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))
    os.replace(tmp_path, path)
