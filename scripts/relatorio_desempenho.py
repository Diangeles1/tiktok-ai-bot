"""Relatorio de desempenho por GANCHO, ARCO e FASE.

Junta o que ja existe (roteiro) com o que a coleta traz (metrica) e responde a
unica pergunta que muda decisao: que escolha de roteiro retem melhor?

Sem metrica coletada, ele mostra so a distribuicao da amostra, que ja serve
para saber se da para comparar: tres videos de um gancho e um de outro nao
comparam nada, por melhor que seja a diferenca aparente.

Uso: python scripts_relatorio.py
"""
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from src.analytics import videos_publicados  # noqa: E402

import glob  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402

# Abaixo disto a diferenca entre dois grupos nao significa nada: com dois ou
# tres videos, uma variacao normal de alcance explica qualquer coisa.
MINIMO_PARA_COMPARAR = 5


def carregar() -> list[dict]:
    """Metrica ja coletada, se houver; senao so o roteiro."""
    coletadas = {}
    for f in glob.glob(os.path.join("output", "*", "metricas.json")):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
            coletadas[d["video_id"]] = d
    saida = []
    for v in videos_publicados():
        reg = coletadas.get(v["video_id"], {})
        saida.append({
            "id": v["video_id"],
            "gancho": v["metadata"].get("gancho"),
            "arco": v["metadata"].get("arco"),
            "fase": v["metadata"].get("fase"),
            "metricas": reg.get("metricas", {}),
        })
    return saida


def main() -> int:
    videos = carregar()
    com_metrica = [v for v in videos if v["metricas"] and not v["metricas"].get("sem_dados")]

    print(f"{len(videos)} videos publicados, {len(com_metrica)} com metrica coletada\n")

    for campo in ("gancho", "arco", "fase"):
        grupos = defaultdict(list)
        for v in videos:
            grupos[v[campo] or "(sem)"].append(v)

        print(f"=== por {campo} ===")
        for nome, itens in sorted(grupos.items(), key=lambda x: -len(x[1])):
            medidos = [i for i in itens
                       if i["metricas"] and not i["metricas"].get("sem_dados")]
            if medidos:
                pct = sum(i["metricas"].get("averageViewPercentage", 0)
                          for i in medidos) / len(medidos)
                views = sum(i["metricas"].get("views", 0) for i in medidos)
                extra = f"  {pct:.0f}% assistido, {views} views"
            else:
                extra = "  (sem metrica)"
            aviso = "" if len(itens) >= MINIMO_PARA_COMPARAR else "   amostra pequena"
            print(f"  {nome:20s} {len(itens):2d} videos{extra}{aviso}")
        print()

    if not com_metrica:
        print("NENHUMA METRICA COLETADA AINDA.")
        print("A comparacao acima e so de amostra: ela diz o que DA para")
        print("comparar quando o dado chegar, nao o que funciona.")
        print()
        print("Para coletar, a autorizacao do Google precisa ser refeita uma")
        print("vez para incluir a leitura de Analytics:")
        print("    python -m src.youtube_oauth_setup")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
