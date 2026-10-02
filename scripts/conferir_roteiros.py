"""Confere se os roteiros ja gerados cumprem as regras "NUNCA" do proprio prompt.

POR QUE ISTO EXISTE: o prompt tem regras explicitas que o modelo ignora, e nada
no projeto conferia. Medido em 2026-10-01: de 34 execucoes com narracao em
disco, 11 (32%) quebravam pelo menos uma. Duas chegaram a publicar o TEXTO da
instrucao dentro da historia ("deixando a pergunta no ar"), o que o espectador
ouve.

Opiniao nao entra aqui. Cada regra conferida esta escrita no prompt, com a
linha onde mora, e o script so diz se foi cumprida.

Uso:  python scripts/conferir_roteiros.py
      python scripts/conferir_roteiros.py output/uma_pasta
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A definicao das regras mora em UM lugar: src/script_gen.py, que e quem as
# aplica na geracao. Este script so mede os roteiros que ja existem. Duplicar
# os padroes aqui criaria duas versoes da mesma regra em arquivos diferentes,
# que foi exatamente o bug das duas constantes de volume que ninguem conferia.
from src.script_gen import regras_do_fecho_quebradas  # noqa: E402


def narracao_de(pasta: str) -> list[str]:
    caminho = os.path.join(pasta, "metadata.json")
    if not os.path.exists(caminho):
        return []
    try:
        with io.open(caminho, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    narracao = meta.get("narracao") or []
    if isinstance(narracao, str):
        return [narracao]
    return [str(x) for x in narracao]


def main() -> int:
    if len(sys.argv) > 1:
        pastas = sys.argv[1:]
    else:
        pastas = sorted(os.path.dirname(p)
                        for p in glob.glob(os.path.join("output", "*", "metadata.json")))

    contagem: dict[str, int] = {}
    com_defeito = []
    total = 0

    for pasta in pastas:
        narracao = narracao_de(pasta)
        if not narracao:
            continue
        total += 1
        # a mesma funcao que a geracao usa, recebendo cenas no formato dela
        quebradas = regras_do_fecho_quebradas([{"narration": n} for n in narracao])
        for nome in quebradas:
            contagem[nome] = contagem.get(nome, 0) + 1
        if quebradas:
            com_defeito.append((os.path.basename(pasta), quebradas, narracao[-1]))

    if not total:
        print("nenhuma narracao encontrada em output/*/metadata.json")
        return 0

    print(f"{total} execucoes com narracao\n")
    for nome in sorted(contagem, key=contagem.get, reverse=True):
        n = contagem[nome]
        print(f"  {nome:<40} {n:>3}  ({n/total:.0%})")
    if not contagem:
        print("  nenhuma regra do fecho quebrada")
    print(f"\n{len(com_defeito)} de {total} com pelo menos um "
          f"({len(com_defeito)/total:.0%})")

    if com_defeito:
        print()
        for nome, quebradas, ultima in com_defeito:
            print(f"  {nome}")
            print(f"    {' + '.join(quebradas)}")
            print(f"    ultima frase: ...{ultima[-90:].strip()}")

    # saida 0 sempre: isto mede o que JA foi gerado, nao reprova. Quem reprova e
    # o validador na hora da geracao (generate_scene_script, que agora recusa o
    # roteiro e pede de novo). Os defeitos listados aqui sao de antes dele
    # existir: nao da para consertar roteiro publicado.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
