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
import re
import sys

# "A ultima frase NUNCA e pergunta" (src/script_gen.py, regra 4 da abertura)
def fecha_com_pergunta(narracao: list[str]) -> bool:
    return bool(narracao) and narracao[-1].rstrip().endswith("?")


# "nunca e formula vaga do tipo 'qual sera o...'": chamar o proximo video troca
# o fecho da historia por anuncio, e em formato curto isso derruba o fim
TEASER = re.compile(
    r"pr[oó]xim[ao]\s+(hist[oó]ria|cap[ií]tulo|v[ií]deo)"
    r"|qual\s+ser[aá]\s+a\s+pr[oó]xim"
    r"|descubra\s+no\s+pr[oó]xim",
    re.IGNORECASE,
)

# o pior dos tres: o modelo escreve a INSTRUCAO em vez de cumprir ela
VAZAMENTO = re.compile(
    r"deixando\s+(a|uma)\s+pergunta\s+no\s+ar"
    r"|deixando\s+o\s+sil[eê]ncio\s+perguntar"
    r"|sem\s+fazer\s+a\s+pergunta",
    re.IGNORECASE,
)

REGRAS = [
    ("fecha com pergunta", lambda n: fecha_com_pergunta(n)),
    ("chama o proximo video", lambda n: bool(TEASER.search(" ".join(n)))),
    ("INSTRUCAO vazou para a narracao", lambda n: bool(VAZAMENTO.search(" ".join(n)))),
]


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

    contagem = {nome: 0 for nome, _ in REGRAS}
    com_defeito = []
    total = 0

    for pasta in pastas:
        narracao = narracao_de(pasta)
        if not narracao:
            continue
        total += 1
        quebradas = [nome for nome, confere in REGRAS if confere(narracao)]
        for nome in quebradas:
            contagem[nome] += 1
        if quebradas:
            com_defeito.append((os.path.basename(pasta), quebradas, narracao[-1]))

    if not total:
        print("nenhuma narracao encontrada em output/*/metadata.json")
        return 0

    print(f"{total} execucoes com narracao\n")
    for nome, _ in REGRAS:
        n = contagem[nome]
        print(f"  {nome:<34} {n:>3}  ({n/total:.0%})")
    print(f"\n{len(com_defeito)} de {total} com pelo menos um "
          f"({len(com_defeito)/total:.0%})")

    if com_defeito:
        print()
        for nome, quebradas, ultima in com_defeito:
            print(f"  {nome}")
            print(f"    {' + '.join(quebradas)}")
            print(f"    ultima frase: ...{ultima[-90:].strip()}")

    # saida 0 sempre: isto mede, nao reprova. Quem reprova e o validador no
    # momento da geracao, se e quando ele for escrito (ver experimentos.md).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
