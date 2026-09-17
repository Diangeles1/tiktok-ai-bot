# tiktok-ai-bot

Bot que gera um video curto por dia (roteiro + narracao + imagens, tudo por IA)
e publica no **TikTok** e no **YouTube Shorts** usando as **APIs oficiais**
de cada plataforma, via GitHub Actions (cron diario). Nao usa scraping nem
automacao de navegador — isso viola os Termos de Servico das plataformas e
arrisca banir a conta.

## Como funciona

```
Groq (LLM gratuito)  -> roteiro (cenas + legenda + hashtags)
edge-tts (gratuito)  -> narracao em audio de cada cena
Pollinations.ai (gratuito) -> imagem de cada cena + legenda "queimada" na imagem
MoviePy/ffmpeg       -> monta o video vertical final (1080x1920)
TikTok Content Posting API   -> publica no TikTok
YouTube Data API v3          -> publica no YouTube Shorts
```

O mesmo video gerado e enviado para as duas plataformas. Cada uma e
independente (`tiktok.enabled` / `youtube.enabled` em `config.yaml`) — se uma
falhar ou nao estiver configurada, a outra continua normalmente.

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

### 4. Crie o app no TikTok for Developers

- https://developers.tiktok.com/apps > Create app
- Adicione o produto **Content Posting API** (e **Login Kit**)
- Em Login Kit > Redirect URI, cadastre a URL do passo 2
- Anote `Client key` e `Client secret`

### 5. Gere o primeiro refresh token (roda so uma vez, na sua maquina)

```bash
pip install -r requirements.txt
python -m src.oauth_setup
```

O script vai pedir `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` e o
`redirect_uri` do passo 2, abrir a URL de autorizacao (voce loga com a conta
do TikTok que vai postar), e pedir que voce cole o `code` que aparece na
pagina de callback. No final ele imprime o `TIKTOK_REFRESH_TOKEN`.

### 6. Crie um GitHub Personal Access Token (para o bot atualizar o token do TikTok sozinho)

O `refresh_token` do TikTok pode mudar a cada renovacao. Para o bot continuar
funcionando sem voce intervir toda semana, ele atualiza o secret sozinho via
API do GitHub. (O refresh_token do YouTube nao precisa disso — o Google nao
rotaciona a cada uso.)

- GitHub > Settings > Developer settings > Personal access tokens (classic)
- Escopo: `repo`
- Guarde como `GH_PAT`

### 7. Crie o projeto no Google Cloud e o app do YouTube

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

### 8. Gere o refresh token do YouTube (roda so uma vez, na sua maquina)

```bash
python -m src.youtube_oauth_setup
```

O script abre o navegador para voce logar com a conta do YouTube que vai
receber os Shorts, e no final imprime o `YOUTUBE_REFRESH_TOKEN`.

### 9. Cadastre os Secrets no repositorio

Settings > Secrets and variables > Actions > New repository secret:

| Nome | Valor |
|---|---|
| `GROQ_API_KEY` | do passo 3 |
| `TIKTOK_CLIENT_KEY` | do passo 4 |
| `TIKTOK_CLIENT_SECRET` | do passo 4 |
| `TIKTOK_REFRESH_TOKEN` | do passo 5 |
| `GH_PAT` | do passo 6 |
| `YOUTUBE_CLIENT_ID` | do passo 7 |
| `YOUTUBE_CLIENT_SECRET` | do passo 7 |
| `YOUTUBE_REFRESH_TOKEN` | do passo 8 |

Se voce quiser usar so uma das duas plataformas, deixe os secrets da outra
vazios e desative-a em `config.yaml` (`tiktok.enabled: false` ou
`youtube.enabled: false`).

### 10. Teste manualmente antes de deixar no automatico

Actions > Daily AI video post > Run workflow > `dry_run: true` primeiro
(gera o video mas nao publica em nenhuma plataforma), confira o artifact
`video-*` gerado. Depois rode com `dry_run: false` para publicar de verdade
(TikTok vai para o seu perfil como privado/SELF_ONLY; YouTube sai publico).

O cron ja esta configurado para rodar todo dia as 10h (horario de Brasilia).

## Customizacao

- `config.yaml`: mude `niche` para o tema do canal, quantidade de cenas,
  vozes do TTS, hashtags fixas, e ligue/desligue cada plataforma.
- `src/script_gen.py`: ajuste o prompt do roteiro (tom, formato, idioma).
- Depois que o app for auditado pela TikTok, mude `tiktok.privacy_level` em
  `config.yaml` para `PUBLIC_TO_EVERYONE`.

## Rodando localmente

```bash
cp .env.example .env   # preencha os valores
pip install -r requirements.txt
export $(cat .env | xargs)   # ou use `python-dotenv` / direnv
DRY_RUN=true python main.py
```
