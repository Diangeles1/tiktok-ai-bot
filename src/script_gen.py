"""Geracao do roteiro diario (texto) usando a API gratuita da Groq."""
import datetime
import json
import math
import os
import random

from groq import BadRequestError, Groq

MODEL = "openai/gpt-oss-120b"
MIN_NARRATION_WORDS = 170
MAX_ATTEMPTS = 3      # tentativas por narracao curta demais
JSON_ATTEMPTS = 3     # tentativas por JSON invalido devolvido pelo modelo
MIN_SCENES = 8
MAX_SCENES = 14

# O gpt-oss e um modelo de raciocinio. No esforco padrao ele gasta o orcamento
# de tokens raciocinando e o modo JSON falha com "Failed to generate JSON";
# medido: com esforco baixo o roteiro sai igual e gasta cinco vezes menos token.
# Troque para None se mudar para um modelo que nao aceite este parametro.
REASONING_EFFORT = "low"
MAX_COMPLETION_TOKENS = 8000

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
- A primeira frase decide se a pessoa fica ou rola o feed. Ela tem que valer
  sozinha, em menos de dois segundos de fala. Nao comece apresentando contexto
  ("havia um homem chamado", "em uma terra distante", "muitos anos atras"):
  isso e o jeito mais rapido de perder o espectador.
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
- Prefira plano aberto ou medio, mostrando lugar e objeto. Evite close de parte
  do corpo (maos, olhos, rosto): nesse gerador o close costuma virar um rosto
  aleatorio que nao tem nada a ver com a cena.
- A imagem da PRIMEIRA cena tem que ser a mais impactante de todas. Ela aparece
  junto com a primeira frase e segura o espectador tanto quanto o texto.
- Sem rosto de pessoa real ou celebridade, sem logo nem marca registrada.
- O visual precisa combinar com o que esta sendo narrado naquele trecho.

Responda APENAS com um JSON valido no formato:
{{
  "topic": "assunto especifico do video de hoje",
  "caption": "legenda curta e chamativa (max 150 caracteres)",
  "thumbnail": "3 a 6 palavras de impacto para a capa, em caixa alta",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"],
  "scenes": [
    {{"narration": "trecho narrado desta cena", "visual": "image prompt in English"}}
  ]
}}
"""


# O modelo as vezes devolve pontuacao tipografica no lugar da comum: hifen
# nao-separavel, travessao, aspa curva, reticencia de um caractere so. Isso
# quebra em tres lugares: a fonte da legenda pode nao ter o glifo e desenhar um
# quadrado, o edge-tts tropeca na leitura, e no console do Windows o print
# levanta UnicodeEncodeError e derruba a execucao inteira.
_PUNCTUATION_FIXES = {
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2015: "-",
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"',
    0x2026: "...", 0x00A0: " ", 0x202F: " ", 0x2009: " ",
    0x200B: "", 0x200C: "", 0x200D: "", 0x2060: "", 0xFEFF: "",
}


def sanitize(value):
    """Troca pontuacao tipografica pela equivalente comum, em todo texto que o
    modelo devolveu (funciona recursivamente em dict e lista)."""
    if isinstance(value, str):
        return value.translate(_PUNCTUATION_FIXES)
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


def _is_malformed_json_error(exc: Exception) -> bool:
    """O modelo as vezes emite JSON quebrado (ja vimos aspa de abertura faltando
    no meio do objeto) e a Groq responde 400 json_validate_failed. E intermitente
    e vale tentar de novo; erro de chave ou de cota nao vale, tem que falhar na
    hora em vez de queimar tentativas."""
    if isinstance(exc, json.JSONDecodeError):
        return True
    return isinstance(exc, BadRequestError) and "json_validate_failed" in str(exc)


def _ask_for_json(client: Groq, model: str, prompt: str) -> dict:
    """Pede o roteiro em JSON e devolve o dict. Ver REASONING_EFFORT: sem ele o
    modo JSON deste modelo falha sempre."""
    params = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "response_format": {"type": "json_object"},
        "max_tokens": MAX_COMPLETION_TOKENS,
    }
    if REASONING_EFFORT:
        params["reasoning_effort"] = REASONING_EFFORT

    for attempt in range(1, JSON_ATTEMPTS + 1):
        try:
            content = client.chat.completions.create(**params).choices[0].message.content
            return sanitize(json.loads(content))
        except Exception as exc:
            if not _is_malformed_json_error(exc) or attempt == JSON_ATTEMPTS:
                raise
            print(f"  [script] o modelo devolveu JSON invalido, tentando de novo "
                  f"({attempt}/{JSON_ATTEMPTS}).")


def _request_scene_script(client: Groq, model: str, niche: str, language: str,
                           min_words: int, max_words: int, seed_topic: str | None,
                           extra_rules: str | None = None,
                           hook: dict | None = None) -> dict:
    prompt = SCENE_PROMPT_TEMPLATE.format(
        niche=niche, language=language, min_words=min_words, max_words=max_words,
        min_scenes=MIN_SCENES, max_scenes=MAX_SCENES,
    )
    if extra_rules:
        prompt += f"\nRegras adicionais deste canal:\n{extra_rules}\n"
    if hook:
        prompt += (f"\nFormato obrigatorio da primeira frase: {hook['instruction']}\n")
    if seed_topic:
        prompt += f"\nTema de hoje (mantenha este tema): {seed_topic}\n"
    else:
        prompt += f"\nEvite temas obvios/repetidos. Semente aleatoria: {random.randint(1, 999999)}\n"

    data = _ask_for_json(client, model, prompt)

    scenes = data.get("scenes")
    if not scenes or not isinstance(scenes, list):
        raise ValueError(f"Resposta do LLM sem lista de cenas: {data}")
    for scene in scenes:
        if not scene.get("narration") or not scene.get("visual"):
            raise ValueError(f"Cena incompleta na resposta do LLM: {scene}")

    return data


def scene_word_count(script: dict) -> int:
    return sum(len(scene["narration"].split()) for scene in script["scenes"])


def current_slot(hours_utc: list[int], now: datetime.datetime | None = None) -> int:
    """Descobre qual publicacao do dia esta rodando, pelo horario mais proximo.

    Deduzir do relogio evita ter que passar o indice pelo workflow, e funciona
    igual quando a execucao e disparada na mao."""
    if not hours_utc:
        return 0
    now = now or datetime.datetime.now(datetime.timezone.utc)
    minutes = now.hour * 60 + now.minute

    def distance(hour: int) -> int:
        diff = abs(minutes - hour * 60)
        return min(diff, 1440 - diff)   # o dia e circular: 23h esta perto de 0h

    return min(range(len(hours_utc)), key=lambda i: distance(hours_utc[i]))


def _spread_stride(total: int) -> int:
    """Passo usado para pular pela lista de temas em vez de seguir na ordem.

    A lista vem agrupada por assunto, entao seguir em ordem publicaria tres
    historias parecidas seguidas. O passo precisa ser coprimo com o total,
    senao parte dos temas nunca seria sorteada."""
    for candidate in range(max(1, total // 3), total):
        if math.gcd(candidate, total) == 1:
            return candidate
    return 1


def hook_of_the_slot(hooks: list[dict], today: datetime.date | None = None,
                      slot_index: int = 0, slot_count: int = 1) -> dict | None:
    """Escolhe o estilo de abertura da vez, girando pela lista.

    Girar serve para medir: com um estilo fixo em todo video nao da para saber
    qual prende mais. Como a quantidade de estilos e muito menor que a de temas,
    cada estilo acaba testado em temas variados, o que separa o efeito do gancho
    do efeito da historia."""
    if not hooks:
        return None
    day = (today or datetime.date.today()).toordinal()
    return hooks[(day * max(1, slot_count) + slot_index) % len(hooks)]


def topic_of_the_day(topics: list[str], today: datetime.date | None = None,
                      slot_index: int = 0, slot_count: int = 1) -> str | None:
    """Escolhe o tema girando pela lista, um por publicacao.

    Sem isso o modelo repetiria sempre as historias mais famosas. O indice
    considera o horario da publicacao, senao as varias execucoes do mesmo dia
    sairiam com o mesmo tema. Usa o dia absoluto (toordinal) em vez do dia do
    ano, senao a virada de ano reiniciaria o ciclo no meio. E deterministico:
    nao guarda estado entre execucoes."""
    if not topics:
        return None
    day = (today or datetime.date.today()).toordinal()
    position = day * max(1, slot_count) + slot_index
    return topics[(position * _spread_stride(len(topics))) % len(topics)]


def generate_scene_script(niche: str, language: str, seed_topic: str | None = None,
                           model: str = MODEL, min_words: int = MIN_NARRATION_WORDS,
                           max_words: int = 220, extra_rules: str | None = None,
                           hook: dict | None = None) -> dict:
    """Gera o roteiro do dia dividido em cenas, para o formato narrado sobre
    imagens que mudam. Mesma politica de retentativa do formato de personagem:
    narracao curta demais nao passa de 1 minuto e perde a monetizacao."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    best = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data = _request_scene_script(client, model, niche, language, min_words,
                                      max_words, seed_topic, extra_rules, hook)
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

    data = _ask_for_json(client, model, prompt)

    if not data.get("narration"):
        raise ValueError(f"Resposta do LLM sem narracao valida: {data}")

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
