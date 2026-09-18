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
fim da chave e a Groq recusa (por isso `export $(cat .env | xargs)` quebra).

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

## Pelo painel

    python painel.py --sem-navegador --porta 8765

Le o `.env` sozinho e roda o mesmo `main.py` com `DRY_RUN=true` e uma pasta
propria (`output/painel_<data>_<hora>/`), entao nao sobrescreve nada. Abra
`http://127.0.0.1:8765/` e clique em Gerar: etapas, cenas e log aparecem ao
vivo, e e o `[n/5]` do log que move a barra de etapas.

Para testar o botao de publicar sem risco, suba outro painel com
`--env arquivo_falso` contendo chaves falsas mais `HTTPS_PROXY` e `HTTP_PROXY`
apontando para `http://127.0.0.1:9`: `requests` e `httplib2` respeitam o proxy,
entao nenhuma chamada sai da maquina e as duas plataformas falham com
ProxyError. Nunca clique em Publicar com o `.env` real.

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
- `--publicar` sem as chaves da plataforma: mensagem nomeando as chaves, sem
  chamada de rede, saida 1
- `max_narration_words` nao e validado, so entra no prompt: a duracao varia
  bastante entre execucoes do mesmo tema

Restaure o config depois: `git checkout config.yaml`.
