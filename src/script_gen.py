"""Geracao do roteiro diario (texto) usando a API gratuita da Groq."""
import datetime
import json
import math
import os
import random
import re
import time

from groq import BadRequestError, Groq, RateLimitError

MODEL = "openai/gpt-oss-120b"
MIN_NARRATION_WORDS = 170
MAX_ATTEMPTS = 3      # tentativas por narracao curta demais
JSON_ATTEMPTS = 3     # tentativas por JSON invalido devolvido pelo modelo
# Esperas pelo limite de tokens por minuto da Groq (plano gratuito: 8.000). Duas
# chamadas seguidas ja estouram, e o bot faz isso quando a narracao sai curta e
# ele tenta de novo na hora. As esperas crescem ate 60s, que zera a janela.
RATE_LIMIT_ATTEMPTS = 5
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
- Antes de escrever, identifique de onde a historia vem: livro, capitulo e
  versiculos da Biblia, ou a fonte da tradicao no caso de santo. Registre no
  campo "passagem" e conte o que ESSA passagem diz. Nao misture detalhes de
  outra historia parecida, e nao preencha lacuna do texto com cliche.
- Nunca peca curtida, compartilhamento ou comentario ("comente amem", "curta
  se voce cre", "compartilhe com quem precisa"). E isca de engajamento: as
  plataformas cortam o alcance de quem usa, e o publico cristao reconhece.
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
- PROIBIDO enquadramento fechado. O campo "visual" NUNCA pode comecar com nem
  conter "close-up", "closeup", "extreme close", "macro shot" ou "detail shot",
  e NUNCA pode ter parte do corpo como assunto (hands, feet, foot, eyes, face,
  fingers, arms, legs, skin, lips, mouth). Nesse gerador o enquadramento fechado
  devolve um rosto aleatorio sem nenhuma relacao com a cena, e o video quebra.
  Todo "visual" comeca por "wide shot", "medium shot" ou "aerial view".
  Para mostrar uma acao, mostre o OBJETO ou o AMBIENTE, nao o membro: em vez de
  "close-up of hands pouring water", escreva "wide shot of a clay jar pouring
  water onto stone"; em vez de "close-up of weary feet in the sand", escreva
  "wide shot of footprints crossing a dune at dusk".
- A imagem da PRIMEIRA cena tem que ser a mais impactante de todas. Ela aparece
  junto com a primeira frase e segura o espectador tanto quanto o texto.
- Sem rosto de pessoa real ou celebridade, sem logo nem marca registrada.
- O visual precisa combinar com o que esta sendo narrado naquele trecho.

Regras da capa (campo "thumbnail"):
- Uma frase curta que se le de uma vez, de 3 a 6 palavras, com gramatica e
  ortografia corretas. Nunca lista de palavras separadas por virgula.
- Escreva em letra normal, NAO em caixa alta: o programa converte depois.
- A capa resume a historia DESTE video, e nao outro episodio do mesmo
  personagem. Prefira palavras que aparecem na sua propria narracao.

Responda APENAS com um JSON valido no formato:
{{
  "topic": "assunto especifico do video de hoje",
  "passagem": "livro, capitulo e versiculos da historia contada, ou a fonte da tradicao",
  "caption": "legenda curta e chamativa (max 150 caracteres)",
  "thumbnail": "frase de capa com 3 a 6 palavras, em letra normal",
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


def _is_daily_limit(exc: Exception) -> bool:
    """Limite diario (tokens ou requisicoes por dia) nao se resolve esperando
    alguns segundos: tentar de novo so atrasaria uma falha inevitavel."""
    return "per day" in str(exc)


def _rate_limit_wait(exc: Exception, attempt: int) -> float:
    """Quanto esperar antes de tentar de novo, em segundos.

    Usa o maior entre o que a Groq pede no cabecalho e uma espera que dobra a
    cada tentativa (5, 10, 20, 40, 60). So o cabecalho nao basta: ele pediu
    menos de 1s no teste, e o proprio SDK da Groq ja tinha tentado de novo com
    esperas curtas e falhado duas vezes antes de devolver o erro."""
    backoff = 5.0 * 2 ** (attempt - 1)
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    for key, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        try:
            backoff = max(backoff, float(headers.get(key)) * scale + 1.0)
            break
        except (TypeError, ValueError):
            continue
    return min(60.0, backoff)


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

    # contadores separados: esperar pelo limite nao gasta tentativa de JSON
    attempt = 0
    rate_limited = 0
    while True:
        try:
            content = client.chat.completions.create(**params).choices[0].message.content
            return sanitize(json.loads(content))
        except RateLimitError as exc:
            rate_limited += 1
            if _is_daily_limit(exc) or rate_limited > RATE_LIMIT_ATTEMPTS:
                raise
            wait = _rate_limit_wait(exc, rate_limited)
            print(f"  [script] limite de tokens por minuto da Groq, esperando {wait:.0f}s "
                  f"({rate_limited}/{RATE_LIMIT_ATTEMPTS}).")
            time.sleep(wait)
        except Exception as exc:
            attempt += 1
            if not _is_malformed_json_error(exc) or attempt >= JSON_ATTEMPTS:
                raise
            print(f"  [script] o modelo devolveu JSON invalido, tentando de novo "
                  f"({attempt}/{JSON_ATTEMPTS}).")


def _request_scene_script(client: Groq, model: str, niche: str, language: str,
                           min_words: int, max_words: int, seed_topic: str | None,
                           extra_rules: str | None = None,
                           hook: dict | None = None, arc: dict | None = None,
                           min_scenes: int = MIN_SCENES, max_scenes: int = MAX_SCENES,
                           cta: str | None = None) -> dict:
    prompt = SCENE_PROMPT_TEMPLATE.format(
        niche=niche, language=language, min_words=min_words, max_words=max_words,
        min_scenes=min_scenes, max_scenes=max_scenes,
    )
    if extra_rules:
        prompt += f"\nRegras adicionais deste canal:\n{extra_rules}\n"
    if hook:
        prompt += (f"\nFormato obrigatorio da primeira frase (fiel a passagem: sem inventar fato nem exagerar detalhe para chamar atencao): {hook['instruction']}\n")
    if arc:
        prompt += (f"\nEstrutura obrigatoria da historia: {arc['instruction']}\n")
    if cta:
        prompt += (f"\nChamada para acao: {cta}\n")
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

    enforce_wide_framing(scenes)
    return data


# Enquadramento fechado quebra o gerador: pedir close de parte do corpo devolve
# um rosto aleatorio sem relacao com a cena. A regra existe no prompt, mas o
# modelo desobedeceu em 3 de 4 execucoes reais, entao a trava e no codigo.
_CLOSEUP_RE = re.compile(
    r"\b(?:extreme\s+|tight\s+)?(?:close[\s-]?ups?|macro\s+shots?|detail\s+shots?)\b",
    re.IGNORECASE)
_BODY_RE = re.compile(
    r"\b(?:hands?|feet|foot|eyes?|faces?|fingers?|arms?|legs?|skin|lips?|mouth|"
    r"palms?|shoulders?|forearms?)\b", re.IGNORECASE)


def enforce_wide_framing(scenes: list[dict]) -> int:
    """Troca enquadramento fechado por plano aberto. Devolve quantas cenas mudou.

    Reescrever e melhor que gerar o roteiro de novo: a narracao ja esta boa e o
    problema e so a descricao da imagem, entao corrigir sai de graca em vez de
    queimar mais uma chamada de LLM."""
    fixed = 0
    for i, scene in enumerate(scenes):
        visual = scene.get("visual", "")
        new = _CLOSEUP_RE.sub("wide shot", visual)
        if new != visual:
            print(f"  [script] cena {i + 1}: enquadramento fechado trocado por plano aberto.")
            scene["visual"] = new
            fixed += 1
        if _BODY_RE.search(scene["visual"]):
            print(f"  [script] AVISO: cena {i + 1} ainda cita parte do corpo "
                  f"({_BODY_RE.search(scene['visual']).group(0)}); o gerador pode errar.")
    return fixed


# A capa e a primeira coisa que aparece na prateleira do canal, e erro ali
# custa clique. O modelo errava ortografia ("QUARENTAS NOITES DE SEDA") porque o
# prompt pedia a capa em caixa alta, e modelo de linguagem escreve pior assim.
# Pedindo letra normal (o thumbnail.py converte), 6 de 6 capas de teste sairam
# corretas. Uma checagem por vocabulario da narracao chegou a ser feita e foi
# removida: rejeitou 3 de 6 capas boas por flexao ("revelam" x "revelou"),
# trocou-as por capas piores e nao pegou o unico erro real (capa sobre outro
# episodio). Ficam so as checagens de forma.
_COVER_STOPWORDS = {"a", "o", "as", "os", "e", "de", "da", "do", "das", "dos", "em",
                    "no", "na", "nos", "nas", "um", "uma", "com", "por", "para",
                    "que", "ao", "se"}


def cover_text(script: dict, max_words: int = 6) -> str:
    """Devolve o texto da capa. Se o do modelo vier vazio ou em lista, usa o tema."""
    cover = (script.get("thumbnail") or "").strip()
    if cover and cover.count(",") < 2:
        return cover
    problem = "veio vazia" if not cover else "veio como lista de palavras"

    # O tema e uma frase do proprio modelo, em letra normal. Se precisar cortar,
    # corta na ultima virgula dentro do limite (fim de oracao) e nunca deixa
    # preposicao pendurada: "Naama, o comandante sirio, curado depois" era o
    # corte cego, e virou "Naama, o comandante sirio".
    all_words = script.get("topic", "").split()
    words = all_words[:max_words]
    if len(all_words) > max_words:
        commas = [i for i, w in enumerate(words) if w.endswith(",")]
        if commas and commas[-1] + 1 >= 3:
            words = words[:commas[-1] + 1]
    while words and words[-1].strip(".,;:!?").lower() in _COVER_STOPWORDS:
        words.pop()
    fallback = " ".join(words).strip(".,;:!? ")
    print(f"  [capa] o texto do modelo {problem}; usando o tema: {fallback}")
    return fallback


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


def rotate_by_slot(items: list[dict], today: datetime.date | None = None,
                    slot_index: int = 0, slot_count: int = 1) -> dict | None:
    """Escolhe um item da lista girando por dia e por publicacao.

    Usada para ganchos e para arcos narrativos. Como as duas listas tem
    tamanhos diferentes (5 e 6, que sao coprimos), a combinacao gancho+arco so
    se repete depois de 30 publicacoes, em vez de travar sempre no mesmo par."""
    if not items:
        return None
    day = (today or datetime.date.today()).toordinal()
    return items[(day * max(1, slot_count) + slot_index) % len(items)]


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
                           hook: dict | None = None, arc: dict | None = None,
                           min_scenes: int = MIN_SCENES, max_scenes: int = MAX_SCENES,
                           cta: str | None = None) -> dict:
    """Gera o roteiro do dia dividido em cenas, para o formato narrado sobre
    imagens que mudam. Mesma politica de retentativa do formato de personagem:
    narracao curta demais nao passa de 1 minuto e perde a monetizacao."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    best = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        data = _request_scene_script(client, model, niche, language, min_words,
                                      max_words, seed_topic, extra_rules, hook, arc,
                                      min_scenes, max_scenes, cta)
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
