---
name: verify
description: Como rodar e observar o tiktokbot de ponta a ponta para verificar uma mudanca
---

# Verificar o tiktokbot

Superficie: CLI. `python main.py` e exatamente o que o workflow
`.github/workflows/daily-post.yml` executa.

## Preparar

Nao existe venv no projeto; usa o Python 3.11 global, que ja tem as
dependencias e o ffmpeg no PATH.

Carregue a chave sem abrir o arquivo (Git Bash, na raiz):

    set -a; . <(tr -d '\r' < .env); set +a

O `tr -d '\r'` e obrigatorio: o `.env` esta em CRLF e sem isso o `\r` entra no
fim da chave e a Groq recusa. O README sugere `export $(cat .env | xargs)`, que
quebra por esse motivo.

## Rodar

    DRY_RUN=true python main.py

`DRY_RUN=true` gera tudo e pula a publicacao no TikTok e no YouTube. Sempre use
isso ao verificar: sem a variavel o pipeline publica de verdade.

Leva de 15 a 20 minutos: cerca de 45s por imagem na Pollinations (que responde
500 com frequencia e depende do retry), mais TTS e o render quadro a quadro.
Rode em background.

**O stdout fica bufferizado quando nao e terminal**, entao o log so aparece no
fim. Para acompanhar, olhe os arquivos sendo escritos em
`output/<data>_<slot>/scenes/` em vez do log. Com `python -u` o log sai na hora.

## Onde sai

`output/<data>_<slot>/` com `final.mp4`, `thumbnail.jpg`, `metadata.json`,
mais `scenes/`, `narration/` e `_captions/`. O slot vem do horario UTC mais
proximo de `posting_hours_utc`, entao o mesmo dia e horario sobrescreve a pasta
no lugar. Guarde o `metadata.json` antes de rodar de novo se quiser comparar.

## O que observar no artefato

    ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,width,height -of default=noprint_wrappers=1 output/<dir>/final.mp4

Esperado: 1080x1920, 30fps, h264 + aac.

Para conferir tarja preta (o bug do movimento de camera, ja corrigido), extraia
quadros e olhe o desvio padrao das bordas. Tarja de verdade tem desvio ~0 e
pixels exatamente 0; imagem escura tem variacao.

    ffmpeg -v error -ss 3.5 -i output/<dir>/final.mp4 -frames:v 1 -y quadro.png

## Caminhos de falha que valem probe

- `content_mode` invalido no config.yaml: erro claro nomeando as opcoes, saida 1
- sem `GROQ_API_KEY`: `KeyError` cru, saida 1
- `max_narration_words` nao e validado, so entra no prompt: a duracao varia
  bastante entre execucoes do mesmo tema

Restaure o config depois: `git checkout config.yaml`.
