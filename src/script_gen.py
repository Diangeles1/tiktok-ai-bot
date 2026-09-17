"""Geracao do roteiro diario (texto) usando a API gratuita da Groq."""
import json
import os
import random

from groq import Groq

MODEL = "openai/gpt-oss-120b"
MIN_NARRATION_WORDS = 170
MAX_ATTEMPTS = 3
MIN_SCENES = 8
MAX_SCENES = 14

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


SCENE_PROMPT_TEMPLATE = """Voce e um roteirista de videos narrados para TikTok/YouTube Shorts,
no formato "canal dark": nao existe apresentador, apenas a narracao por cima de
imagens que vao mudando.

Crie UM video novo e ORIGINAL, narrado em {language}, sobre: {niche}

Regras da narracao:
- Somando todas as cenas, de {min_words} a {max_words} palavras (o video precisa
  passar de 1 minuto, requisito minimo de programas de monetizacao).
- Gancho forte na primeira frase, que faca a pessoa parar de rolar o feed.
- Final que deixe a pessoa querendo o proximo video, sem parecer propaganda.
- Fala natural e corrida, sem emoji, sem markdown e sem citar numero de cena.
- Nada ofensivo, discriminatorio, sexual ou perigoso.

Regras das cenas:
- Divida a narracao em {min_scenes} a {max_scenes} cenas, cada uma com 2 a 4 frases.
- Cada cena tem uma descricao visual ("visual") escrita EM INGLES, porque ela vai
  alimentar um gerador de imagens. Descreva coisa concreta: lugar, objeto, clima,
  luz, angulo.
- NUNCA peca imagem que dependa de palavra escrita (placa, carta, cartaz, tela de
  celular, jornal): o gerador nao desenha texto legivel e a cena sai borrada.
  Mostre a mesma ideia por outro caminho, por exemplo uma porta fechada em vez de
  uma placa de "fechado".
- Sem rosto de pessoa real ou celebridade, sem logo nem marca registrada.
- O visual precisa combinar com o que esta sendo narrado naquele trecho.

Responda APENAS com um JSON valido no formato:
{{
  "topic": "assunto especifico do video de hoje",
  "caption": "legenda curta e chamativa (max 150 caracteres)",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"],
  "scenes": [
    {{"narration": "trecho narrado desta cena", "visual": "image prompt in English"}}
  ]
}}
"""


def _request_scene_script(client: Groq, model: str, niche: str, language: str,
                           min_words: int, max_words: int, seed_topic: str | None) -> dict:
    prompt = SCENE_PROMPT_TEMPLATE.format(
        niche=niche, language=language, min_words=min_words, max_words=max_words,
        min_scenes=MIN_SCENES, max_scenes=MAX_SCENES,
    )
    if seed_topic:
        prompt += f"\nTema sugerido para hoje (use como inspiracao): {seed_topic}\n"
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

    scenes = data.get("scenes")
    if not scenes or not isinstance(scenes, list):
        raise ValueError(f"Resposta do LLM sem lista de cenas: {content}")
    for scene in scenes:
        if not scene.get("narration") or not scene.get("visual"):
            raise ValueError(f"Cena incompleta na resposta do LLM: {scene}")

    return data


def scene_word_count(script: dict) -> int:
    return sum(len(scene["narration"].split()) for scene in script["scenes"])


def generate_scene_script(niche: str, language: str, seed_topic: str | None = None,
                           model: str = MODEL, min_words: int = MIN_NARRATION_WORDS,
                           max_words: int = 220) -> dict:
    """Gera o roteiro do dia dividido em cenas, para o formato narrado sobre
    imagens que mudam. Mesma politica de retentativa do formato de personagem:
    narracao curta demais nao passa de 1 minuto e perde a monetizacao."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    best = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data = _request_scene_script(client, model, niche, language,
                                      min_words, max_words, seed_topic)
        word_count = scene_word_count(data)
        if word_count >= min_words:
            return data

        if best is None or word_count > scene_word_count(best):
            best = data
        print(f"  [script] narracao com {word_count} palavras (minimo {min_words}). "
              f"Tentativa {attempt}/{MAX_ATTEMPTS}.")

    print(f"  [script] AVISO: seguindo com {scene_word_count(best)} palavras. "
          f"O video pode ficar abaixo de 1 minuto e nao se qualificar para monetizacao.")
    return best


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
