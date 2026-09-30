"""Confere que uma edicao no config.yaml nao mexeu na ESTRUTURA.

Existe porque isto ja aconteceu: uma substituicao de acentos no arquivo
inteiro renomeou a chave "video" para "video" com acento, levando junto as 11
chaves abaixo dela. O codigo le cfg["video"], entao a geracao teria quebrado
inteira, e nada no terminal avisaria.

Compara o arquivo atual com a versao do ultimo commit e falha se:
  - alguma chave mudou de nome, sumiu ou apareceu;
  - algum valor NAO-texto mudou (numero, booleano, lista de topicos).

Texto pode mudar a vontade: e o prompt, e melhorar o prompt e o trabalho.

Uso:  python .claude/skills/candeia-otimizacao/scripts/conferir_config.py
      python .../conferir_config.py caminho/para/config.yaml
"""
import io
import subprocess
import sys

import yaml


def chaves(no, prefixo=""):
    """Todos os caminhos de chave, achatados: {"video", "video.fps", ...}."""
    achadas = set()
    if isinstance(no, dict):
        for k, v in no.items():
            achadas.add(prefixo + str(k))
            achadas |= chaves(v, prefixo + str(k) + ".")
    elif isinstance(no, list):
        for i, v in enumerate(no):
            achadas |= chaves(v, prefixo + f"[{i}].")
    return achadas


def valores_nao_texto(no, prefixo=""):
    """So numeros, booleanos e nulos. Texto fica de fora de proposito."""
    encontrados = {}
    if isinstance(no, dict):
        for k, v in no.items():
            encontrados.update(valores_nao_texto(v, prefixo + str(k) + "."))
    elif isinstance(no, list):
        for i, v in enumerate(no):
            encontrados.update(valores_nao_texto(v, prefixo + f"[{i}]."))
    elif not isinstance(no, str):
        encontrados[prefixo[:-1]] = no
    return encontrados


def main() -> int:
    caminho = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"

    atual = yaml.safe_load(io.open(caminho, encoding="utf-8"))

    git = subprocess.run(
        ["git", "show", f"HEAD:{caminho}"], capture_output=True
    )
    if git.returncode != 0:
        print(f"nao consegui ler {caminho} do ultimo commit; sem comparacao")
        return 0
    anterior = yaml.safe_load(git.stdout.decode("utf-8"))

    antes, depois = chaves(anterior), chaves(atual)
    sumiram, surgiram = antes - depois, depois - antes

    va, vd = valores_nao_texto(anterior), valores_nao_texto(atual)
    mudados = {k for k in va if k in vd and va[k] != vd[k]}

    print(f"{caminho}: {len(depois)} chaves (antes {len(antes)})")

    if not sumiram and not surgiram and not mudados:
        print("OK: estrutura identica, so texto mudou.")
        return 0

    print("\nREPROVADO")
    for k in sorted(sumiram):
        print(f"  chave sumiu:   {k}")
    for k in sorted(surgiram):
        print(f"  chave surgiu:  {k}")
    for k in sorted(mudados):
        print(f"  valor mudou:   {k}: {va[k]!r} -> {vd[k]!r}")
    print("\nSe a mudanca de chave nao foi intencional, o codigo que le essa")
    print("chave vai parar de achar. Reverta e refaca tocando so os valores.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
