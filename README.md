# tiktok-ai-bot

Bot que gera uma esquete de humor por dia — estrelada por um personagem 3D
fixo e original — e publica no **TikTok** e no **YouTube Shorts** usando as
**APIs oficiais** de cada plataforma, via GitHub Actions (cron diario). Nao
usa scraping nem automacao de navegador — isso viola os Termos de Servico das
plataformas e arrisca banir a conta.

## Como funciona

```
Pollinations.ai (gratuito, 1x so) -> gera e cacheia a imagem do personagem fixo
Groq (LLM gratuito)   -> roteiro (monologo do personagem + legenda + hashtags)
edge-tts (gratuito)   -> narracao + timing de cada palavra
MoviePy/ffmpeg        -> personagem com zoom leve + legendas animadas palavra-a-palavra
TikTok Content Posting API   -> publica no TikTok
YouTube Data API v3          -> publica no YouTube Shorts
```

A MESMA imagem do personagem (gerada uma unica vez e commitada em
`assets/character.png`) e reaproveitada em todo video, pra ele ficar sempre
com a mesma cara. O video final e enviado para as duas plataformas de forma
independente (`tiktok.enabled` / `youtube.enabled` em `config.yaml`) — se uma
falhar ou nao estiver configurada, a outra continua normalmente.

### Por que sem lip-sync (boca sincronizada)?

Deu pra fazer 100% gratuito assim. Um avatar com a boca se mexendo sincronizada
com a voz exige servicos pagos (HeyGen, D-ID, Synthesia). E hoje ha um motivo
a mais pra nao usar: a politica do **TikTok Creator Rewards Program** exclui
explicitamente "conteudo que contenha sincronizacao labial" da definicao de
conteudo original elegivel para monetizacao — entao o formato atual (narracao
+ legenda, sem lip-sync) e o que melhor se encaixa nas regras de hoje.

## Sobre monetizacao (TikTok Creator Rewards Program)

Vale saber antes de esperar renda do bot:

- Precisa de conta pessoal, 18+, **10.000 seguidores** e **100.000
  visualizacoes nos ultimos 30 dias** pra sequer se inscrever no programa.
- Video precisa ter **pelo menos 1 minuto** — por isso o roteiro foi ajustado
  para narracoes de ~170-220 palavras.
- Conteudo de IA nao e proibido, mas precisa contar como "original": nada de
  copiar conteudo de terceiros, watermark de outro app, ou so overlay de texto
  em foto/video alheio. TikTok tambem pede pra rotular conteudo gerado por IA
  (Configuracoes do video > "Rotular como IA" no app, manualmente por enquanto
  — a Content Posting API nao expõe esse campo ainda).
- YouTube tem programa equivalente (YouTube Partner Program), com seus proprios
  requisitos de inscritos/horas assistidas — nao coberto em detalhe aqui.

## Limitacao importante do TikTok

Apps **nao auditados** pela TikTok so podem publicar com `privacy_level =
SELF_ONLY`: o video fica visivel apenas para a propria conta (como um
rascunho), nao aparece publicamente no feed. Para publicar direto ao publico
(`PUBLIC_TO_EVERYONE`), voce precisa solicitar auditoria do app no TikTok for
Developers depois que ele estiver funcionando (Manage Apps > seu app > Submit
for Review). Isso e uma exigencia da TikTok, nao uma limitacao deste bot.

O YouTube Shorts nao tem essa restricao: com o app OAuth do Google em
publishing status **"In production"**, os videos ja saem publicos direto
(configuravel em `youtube.privacy_status`).

O Kwai nao foi incluido porque a Kuaishou/Kwai nao oferece API publica de
postagem para desenvolvedores individuais fora de parcerias comerciais/MCN.

## Setup passo a passo

### 1. Crie o repositorio no GitHub

Suba esta pasta para um repositorio novo (pode ser privado).

### 2. Ative o GitHub Pages (necessario para o OAuth do TikTok)

O TikTok exige redirect_uri em HTTPS (nao aceita `localhost`). Este repo ja
inclui `docs/oauth-callback.html` pronto para isso.

- Settings > Pages > Source: `Deploy from a branch` > Branch: `main` / `docs`
- Sua URL de callback sera algo como:
  `https://SEU-USUARIO.github.io/SEU-REPO/oauth-callback.html`

### 3. Crie a chave gratuita da Groq

- https://console.groq.com/keys > Create API Key
- Guarde como `GROQ_API_KEY`

### 4. Gere a imagem do personagem (uma vez, e commite no repo)

```bash
pip install -r requirements.txt
python -m src.generate_character
git add assets/character.png
git commit -m "Gera personagem do canal"
git push
```

Isso fixa a aparencia do personagem pra sempre (o gerador de imagens gratuito
nao repete o mesmo rosto sozinho a cada chamada). Quer trocar o visual? Edite
`character.description` em `config.yaml` e rode com `--force`.

### 5. Crie o app no TikTok for Developers

- https://developers.tiktok.com/apps > Create app
- Adicione o produto **Content Posting API** (e **Login Kit**)
- Em Login Kit > Redirect URI, cadastre a URL do passo 2
- Anote `Client key` e `Client secret`

### 6. Gere o primeiro refresh token (roda so uma vez, na sua maquina)

```bash
python -m src.oauth_setup
```

O script vai pedir `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` e o
`redirect_uri` do passo 2, abrir a URL de autorizacao (voce loga com a conta
do TikTok que vai postar), e pedir que voce cole o `code` que aparece na
pagina de callback. No final ele imprime o `TIKTOK_REFRESH_TOKEN`.

### 7. Crie um GitHub Personal Access Token (para o bot atualizar o token do TikTok sozinho)

O `refresh_token` do TikTok pode mudar a cada renovacao. Para o bot continuar
funcionando sem voce intervir toda semana, ele atualiza o secret sozinho via
API do GitHub. (O refresh_token do YouTube nao precisa disso — o Google nao
rotaciona a cada uso.)

- GitHub > Settings > Developer settings > Personal access tokens (classic)
- Escopo: `repo`
- Guarde como `GH_PAT`

### 8. Crie o projeto no Google Cloud e o app do YouTube

- https://console.cloud.google.com/ > crie um projeto novo
- APIs e servicos > Biblioteca > ative **"YouTube Data API v3"**
- APIs e servicos > Tela de consentimento OAuth:
  - Tipo de usuario: **External**
  - Escopo adicionado: `https://www.googleapis.com/auth/youtube.upload`
  - **Publicar o app** (botao "Publish app" / mudar de "Testing" para "In
    production"). Isso e essencial: em "Testing" o refresh_token expira em
    7 dias e o bot para de funcionar sozinho.
  - Como o escopo `youtube.upload` e sensivel, o Google pode mostrar um aviso
    de "app nao verificado" para quem faz login — normal para uso pessoal,
    basta clicar em Avancado > Acessar mesmo assim (voce mesmo e quem loga).
- APIs e servicos > Credenciais > Criar credenciais > ID do cliente OAuth >
  tipo **"App para computador" (Desktop app)**
- Anote o `Client ID` e o `Client secret`

### 9. Gere o refresh token do YouTube (roda so uma vez, na sua maquina)

```bash
python -m src.youtube_oauth_setup
```

O script abre o navegador para voce logar com a conta do YouTube que vai
receber os Shorts, e no final imprime o `YOUTUBE_REFRESH_TOKEN`.

### 10. Cadastre os Secrets no repositorio

Settings > Secrets and variables > Actions > New repository secret:

| Nome | Valor |
|---|---|
| `GROQ_API_KEY` | do passo 3 |
| `TIKTOK_CLIENT_KEY` | do passo 5 |
| `TIKTOK_CLIENT_SECRET` | do passo 5 |
| `TIKTOK_REFRESH_TOKEN` | do passo 6 |
| `GH_PAT` | do passo 7 |
| `YOUTUBE_CLIENT_ID` | do passo 8 |
| `YOUTUBE_CLIENT_SECRET` | do passo 8 |
| `YOUTUBE_REFRESH_TOKEN` | do passo 9 |

Se voce quiser usar so uma das duas plataformas, deixe os secrets da outra
vazios e desative-a em `config.yaml` (`tiktok.enabled: false` ou
`youtube.enabled: false`).

### 11. Teste manualmente antes de deixar no automatico

Actions > Daily AI video post > Run workflow > `dry_run: true` primeiro
(gera o video mas nao publica em nenhuma plataforma), confira o artifact
`video-*` gerado. Depois rode com `dry_run: false` para publicar de verdade
(TikTok vai para o seu perfil como privado/SELF_ONLY; YouTube sai publico).

O cron ja esta configurado para rodar todo dia as 10h (horario de Brasilia).

## Customizacao

- `config.yaml`: `character.name`/`character.description` definem o
  personagem (rode `python -m src.generate_character --force` depois de
  mudar a descricao), `niche` o tipo de causo/piada, alem de vozes do TTS,
  hashtags fixas e liga/desliga de cada plataforma.
- `src/script_gen.py`: ajuste o prompt do roteiro (tom, formato, idioma).
- `captions.words_per_chunk` e `video.zoom_effect` controlam o estilo da
  legenda animada e do efeito de zoom.
- Depois que o app for auditado pela TikTok, mude `tiktok.privacy_level` em
  `config.yaml` para `PUBLIC_TO_EVERYONE`.

## Rodando localmente

```bash
cp .env.example .env   # preencha os valores
pip install -r requirements.txt
export $(cat .env | xargs)   # ou use `python-dotenv` / direnv
DRY_RUN=true python main.py
```
