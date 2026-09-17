"""Geracao do roteiro diario (texto) usando a API gratuita da Groq."""
import json
import os
import random

from groq import Groq

MODEL = "openai/gpt-oss-120b"
MIN_NARRATION_WORDS = 170
MAX_ATTEMPTS = 3

PROMPT_TEMPLATE = """Voce e um roteirista de esquetes curtas de humor para TikTok/YouTube Shorts,
estreladas por um personagem fixo chamado "{character_name}".
Sobre o personagem: {character_vibe}

Crie o roteiro de UM video novo e ORIGINAL, em {language}, no formato de
monologo em primeira pessoa do personagem contando um causo/situacao engracada
do dia a dia (tema: {niche}).

Regras:
- Narracao continua (nao dividida em cenas), 170 a 220 palavras (para o video
  ficar com pelo menos 1 minuto, requisito minimo de programas de monetizacao
  como o TikTok Creator Rewards), com gancho forte na primeira frase e uma
  virada/piada no final.
- Escreva como fala natural, sem emojis, sem markdown, sem direcoes de cena.
- Tom leve, familiar, nada ofensivo, discriminatorio, sexual ou perigoso.
- Gere tambem uma legenda curta e chamativa (max 150 caracteres) e 4 hashtags
  relevantes (sem repetir #fyp).

Responda APENAS com um JSON valido no formato:
{{
  "topic": "assunto especifico da esquete de hoje",
  "caption": "legenda curta e chamativa",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"],
  "narration": "texto completo do monologo do personagem"
}}
"""


def _request_script(client: Groq, model: str, character_name: str, character_vibe: str,
                     niche: str, language: str, seed_topic: str | None) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        character_name=character_name, character_vibe=character_vibe,
        niche=niche, language=language,
    )
    if seed_topic:
        prompt += f"\nTema sugerido para hoje (use como inspiracao, mas sinta-se livre para refinar): {seed_topic}\n"
    else:
        prompt += f"\nEvite temas obvios/repetidos. Semente aleatoria: {random.randint(1, 999999)}\n"

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.95,
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content
    data = json.loads(content)

    if not data.get("narration"):
        raise ValueError(f"Resposta do LLM sem narracao valida: {content}")

    return data


def generate_script(character_name: str, character_vibe: str, niche: str,
                     language: str, seed_topic: str | None = None,
                     model: str = MODEL, min_words: int = MIN_NARRATION_WORDS) -> dict:
    """Gera o roteiro do dia. Tenta de novo quando a narracao vem curta demais:
    o video precisa passar de 1 minuto para se qualificar aos programas de
    monetizacao, e o LLM costuma devolver menos palavras do que o pedido."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    best = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data = _request_script(client, model, character_name, character_vibe,
                                niche, language, seed_topic)
        word_count = len(data["narration"].split())
        if word_count >= min_words:
            return data

        if best is None or word_count > len(best["narration"].split()):
            best = data
        print(f"  [script] narracao com {word_count} palavras (minimo {min_words}). "
              f"Tentativa {attempt}/{MAX_ATTEMPTS}.")

    print(f"  [script] AVISO: seguindo com {len(best['narration'].split())} palavras. "
          f"O video pode ficar abaixo de 1 minuto e nao se qualificar para monetizacao.")
    return best
