"""Geracao do roteiro diario (texto) usando a API gratuita da Groq."""
import json
import os
import random

from groq import Groq

MODEL = "llama-3.3-70b-versatile"

PROMPT_TEMPLATE = """Voce e um roteirista de videos curtos para TikTok sobre "{niche}".
Crie o conteudo de UM video novo, ORIGINAL e factualmente correto, em {language}.

Regras:
- {n_scenes} cenas curtas (1-2 frases cada), formando uma narrativa com gancho forte na cena 1.
- Cada cena precisa de um "image_prompt" em ingles, descritivo, para gerar uma imagem (estilo cinematografico, sem texto na imagem).
- O texto de cada cena e o que sera narrado em voz alta: escreva de forma natural para fala, sem emojis, sem markdown.
- Gere tambem um titulo/legenda curto e chamativo (max 150 caracteres) e 4 hashtags relevantes (sem repetir #fyp).
- Nao inclua nada ofensivo, perigoso, medico/financeiro sensivel ou que viole diretrizes de conteudo do TikTok.

Responda APENAS com um JSON valido no formato:
{{
  "topic": "assunto especifico escolhido para hoje",
  "caption": "legenda curta e chamativa",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4"],
  "scenes": [
    {{"text": "narracao da cena 1", "image_prompt": "descricao em ingles para gerar a imagem"}},
    ...
  ]
}}
"""


def generate_script(niche: str, language: str, n_scenes: int, seed_topic: str | None = None) -> dict:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    prompt = PROMPT_TEMPLATE.format(niche=niche, language=language, n_scenes=n_scenes)
    if seed_topic:
        prompt += f"\nTema sugerido para hoje (use como inspiracao, mas sinta-se livre para refinar): {seed_topic}\n"
    else:
        # pequena variação para reduzir repetição entre execuções diárias
        prompt += f"\nEvite temas obvios/repetidos. Semente aleatoria: {random.randint(1, 999999)}\n"

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content
    data = json.loads(content)

    if "scenes" not in data or not data["scenes"]:
        raise ValueError(f"Resposta do LLM sem cenas validas: {content}")

    return data
