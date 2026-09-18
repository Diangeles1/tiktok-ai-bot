"""Normaliza e junta as hashtags do video.

Duas coisas que o LLM erra sozinho e custam alcance: devolve hashtag com
acento, que fragmenta a busca porque quem procura digita sem, e repete tag que
ja esta na lista fixa em outra grafia (#Fe e #fe contam como a mesma, mas
ocupam duas vagas). O YouTube ainda mostra apenas as tres primeiras ao lado do
titulo, entao vaga desperdicada e alcance perdido."""
import re
import unicodedata


def normalize(raw: str) -> str | None:
    """#Historia Biblica -> #HistoriaBiblica. Devolve None se nao sobrar nada."""
    text = raw.strip().lstrip("#")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^0-9A-Za-z]", "", text)
    return f"#{text}" if text else None


def build(*groups: list[str], limit: int = 12) -> list[str]:
    """Junta os grupos na ordem recebida, tirando repetidas e cortando no limite.

    A ordem importa: as primeiras sao as que o YouTube exibe, entao passe
    primeiro as especificas do video, que descrevem melhor o conteudo que as
    tags genericas do canal."""
    seen: set[str] = set()
    result: list[str] = []

    for group in groups:
        for raw in group or []:
            tag = normalize(raw)
            if not tag or tag.lower() in seen:
                continue
            seen.add(tag.lower())
            result.append(tag)
            if len(result) >= limit:
                return result

    return result
