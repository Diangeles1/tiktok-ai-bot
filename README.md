<div align="center">

# tiktok-ai-bot

**Histórias bíblicas narradas, geradas por IA e publicadas sozinhas no TikTok e no YouTube Shorts, três vezes por dia.**

Roteiro em cenas, uma imagem para cada cena, narração com legendas animadas e publicação
pelas APIs oficiais das duas plataformas, rodando de graça no GitHub Actions.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![TikTok](https://img.shields.io/badge/TikTok-Content_Posting_API-000000?style=for-the-badge&logo=tiktok&logoColor=white)](https://developers.tiktok.com/)
[![YouTube](https://img.shields.io/badge/YouTube-Data_API_v3-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://developers.google.com/youtube/v3)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-3x_ao_dia-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-MoviePy-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

[Resultado](#resultado) · [Como funciona](#como-funciona) · [Estratégia](#estratégia-em-duas-fases) · [Publicação](#publicação-no-tiktok) · [Setup](#setup-passo-a-passo) · [Customização](#customização) · [Painel](#painel-local) · [Rodando localmente](#rodando-localmente)

</div>

---

## Resultado

<table>
<tr>
<td width="46%" align="center">

<img src="docs/img/preview.jpg" alt="Quadro de um vídeo gerado pelo bot: figura solitária caminhando por uma trilha no deserto, com legenda animada" width="260">

</td>
<td width="54%">

**O que sai no final:**

+ Vídeo vertical 1080x1920, pronto para Shorts e TikTok
+ Uma imagem por cena, no mesmo estilo visual, com movimento de câmera e transição suave
+ Legendas animadas palavra a palavra, com pontuação e destaque na palavra falada
+ Trilha de fundo e marca d'água com o @ do canal
+ Capa com frase de impacto para o YouTube
+ Três publicações por dia: 06h, 12h e 20h de Brasília

</td>
</tr>
</table>

## Como funciona

<div align="center">
  <img src="docs/img/pipeline.svg" alt="Fluxo do pipeline: Groq escreve o roteiro em cenas, Pollinations gera uma imagem por cena, edge-tts narra, MoviePy monta o vídeo e a capa, e a publicação vai para TikTok e YouTube Shorts" width="100%">
</div>

| # | Ferramenta | O que faz |
|:--:|---|---|
| 1 | ![Groq](https://img.shields.io/badge/Groq-F55036?style=flat-square) | Escreve o roteiro em cenas: narração, descrição visual de cada cena, passagem de origem, título, frase da capa e hashtags |
| 2 | ![Pollinations](https://img.shields.io/badge/Pollinations.ai-7c5cff?style=flat-square) | Gera uma imagem por cena, todas com o mesmo sufixo de estilo para o vídeo não parecer colagem |
| 3 | ![edge-tts](https://img.shields.io/badge/edge--tts-0F9D58?style=flat-square) | Narra cada cena e devolve o tempo de cada palavra, que sincroniza as legendas |
| 4 | ![MoviePy](https://img.shields.io/badge/MoviePy-2B7FFF?style=flat-square&logo=ffmpeg&logoColor=white) | Monta o vídeo: movimento de câmera, transição, legendas, trilha, marca d'água e capa |
| 5 | ![TikTok](https://img.shields.io/badge/TikTok-000000?style=flat-square&logo=tiktok&logoColor=white) | Envia o vídeo para a caixa de entrada do app, onde você finaliza a postagem |
| 6 | ![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=flat-square&logo=youtube&logoColor=white) | Publica o Short com a capa |

As duas plataformas são independentes: os liga/desliga são `tiktok.enabled` e
`youtube.enabled` em `config.yaml`, e se uma falhar ou não estiver configurada, a outra
continua normalmente.

Nada de scraping ou automação de navegador: esse tipo de técnica viola os Termos de
Serviço das plataformas e coloca a conta em risco de banimento.

### O que muda de um vídeo para outro

Cada publicação combina três rotações independentes. Não há banco de dados nem estado
entre execuções: o bot deduz o dia e o horário e escolhe sozinho.

| Rotação | Opções | Para que serve |
|---|---|---|
| Tema | 96 histórias dos Evangelhos, do Antigo Testamento e de santos | Mais de um mês sem repetir história |
| Gancho | 4 estilos de primeira frase | Descobrir qual abertura segura mais o espectador |
| Arco | 7 estruturas narrativas | O mesmo tema volta meses depois contado de outro jeito |

Gancho e arco só repetem a mesma combinação a cada 28 publicações. Cada vídeo grava em
`metadata.json` o gancho, o arco, a fase e a passagem usados. Depois de algumas semanas,
cruze esses dados com a retenção no YouTube Studio e mantenha só o que funciona.

### Cuidados com o conteúdo

O prompt do roteiro tem travas específicas para este nicho:

+ **Passagem declarada.** Antes de narrar, o modelo diz de qual passagem tirou a
  história. Nos testes, isso fez sumir um detalhe inventado que aparecia com frequência, e
  conferir a referência no `metadata.json` é o jeito rápido de pegar uma distorção
+ **Palavras próprias.** Nada de versículo literal de tradução moderna, que é protegida
  por direito autoral e ainda derruba a originalidade exigida pela monetização
+ **Respeito.** Nenhuma comparação ou ataque a outra religião, denominação ou crença
+ **Plano aberto.** Sem rosto de figura sagrada e sem close de mãos: o gerador de
  imagem erra anatomia com frequência e o resultado fica irreverente. Um filtro troca por
  plano aberto o close que escapar do prompt
+ **Sem isca de engajamento.** O roteiro não pede "comente amém" nem nada parecido

## Estratégia em duas fases

O TikTok Creator Rewards só paga vídeo com mais de 1 minuto, e só para conta que já
bateu os requisitos. Antes disso, vídeo longo não rende nada e ainda custa retenção.
Por isso o bot trabalha em duas fases:

| | `crescimento` | `monetizacao` |
|---|---|---|
| Objetivo | Ganhar seguidores | Render no Creator Rewards |
| Narração | 90 a 115 palavras (35 a 44s) | 168 a 220 palavras (acima de 60s) |
| Cenas | 5 a 8 | 8 a 14 |
| Duração mínima | Nenhuma | 60s, com aviso no log se ficar abaixo |
| Fechamento | Pede para seguir o canal | Convite curto para a próxima história |

A fase ativa é a linha `fase` em `config.yaml`. Troque para `"monetizacao"` quando a
conta for aceita no programa.

## Sobre monetização

| Requisito do TikTok Creator Rewards | Situação |
|---|---|
| Conta pessoal, 18 anos ou mais | Depende de você |
| 10.000 seguidores | É o objetivo da fase de crescimento |
| 100.000 visualizações em 30 dias | Depende do alcance |
| Vídeo com mais de 1 minuto | Coberto na fase de monetização: o roteiro é gerado de novo se vier curto, e o log avisa se a narração ficar abaixo de 60s |
| Conteúdo original, sem marca d'água de terceiros | Coberto: roteiro recontado com palavras próprias, imagens geradas para cada vídeo e marca da Pollinations removida |
| Rotular conteúdo gerado por IA | No modo upload, você ativa o rótulo ao finalizar a postagem no celular |

O YouTube tem um programa equivalente (YouTube Partner Program), com seus próprios
requisitos de inscritos e horas assistidas, não detalhados aqui.

## Publicação no TikTok

Apps **não auditados** pelo TikTok só publicam direto como privado (`SELF_ONLY`). Para
contornar isso sem esperar a auditoria, o bot tem dois modos, escolhidos em `tiktok.mode`:

| Modo | Como funciona | Escopo | Quando usar |
|---|---|---|---|
| `upload` (padrão) | O vídeo chega na caixa de entrada do app do TikTok e você finaliza a postagem no celular, escolhendo legenda, som e privacidade | `video.upload` | Enquanto o app não for auditado. Como quem publica é você, o vídeo sai público |
| `direct` | O bot publica sozinho | `video.publish` | Depois da auditoria. Antes dela, só publica como privado |

**Rotina no modo upload.** O TikTok limita os envios pendentes (no máximo 5 em 24
horas). Com três vídeos por dia, finalize os rascunhos todo dia para não travar os
próximos envios. A legenda sugerida, já com as hashtags, aparece no log da execução e
no campo `legenda_tiktok` do `metadata.json`.

**Publicar direto pelo painel.** Com `tiktok.painel_direto: true`, o painel tem a tela de
publicar direto no perfil que a revisão do TikTok exige:

+ mostra a conta que vai receber o post, com nome e foto
+ deixa editar a legenda e as hashtags
+ "Quem pode ver" começa vazio e só oferece as opções que a conta permite
+ comentário, dueto e costura começam desmarcados, e ficam travados se a conta desligou
+ divulgação de conteúdo comercial ("Sua marca" e "Conteúdo de marca"), com o rótulo que
  o vídeo vai receber; conteúdo de marca não pode sair como "Somente eu"
+ rótulo de conteúdo gerado por IA, ligado por padrão
+ o aviso da Confirmação de Uso de Música antes de publicar, e depois o aviso de que o
  TikTok pode levar alguns minutos para processar o vídeo

As mesmas regras são conferidas de novo no servidor do painel, com a conta consultada na
hora. O TikTok pede que a pessoa confirme cada post, então o horário automático continua
no modo `upload` e a publicação direta é a do painel.

**Para sair público direto,** ligue o **Direct Post** no Content Posting API do app,
reconecte a conta (passo 6, que passa a pedir `video.publish`) e envie o app para revisão
(Manage Apps > seu app > Submit for Review). Os textos para a ficha e o roteiro do vídeo
de demonstração estão em [revisao_tiktok.md](revisao_tiktok.md). Até a aprovação, a
publicação direta só sai como "Somente eu". Quando o TikTok aprovar, mude
`tiktok.app_aprovado` para `true` e o painel passa a abrir na publicação direta.

O YouTube Shorts não tem essa restrição: com o app OAuth do Google em publishing status
**"In production"**, os vídeos já saem públicos direto (configurável em
`youtube.privacy_status`).

O Kwai não foi incluído porque a Kuaishou/Kwai não oferece API pública de postagem para
desenvolvedores individuais fora de parcerias comerciais/MCN.

## Setup passo a passo

### 1. Crie o repositório no GitHub

Suba esta pasta para um repositório novo (pode ser privado). Os horários automáticos só
disparam a partir da branch padrão (`main`), então é nela que o código precisa estar.

### 2. Ative o GitHub Pages (necessário para o OAuth do TikTok)

O TikTok exige `redirect_uri` em HTTPS (não aceita `localhost`). Este repo já inclui
`docs/oauth-callback.html` pronto para isso.

- Settings > Pages > Source: `Deploy from a branch` > Branch: `main` / `docs`
- Sua URL de callback será algo como: `https://SEU-USUARIO.github.io/SEU-REPO/oauth-callback.html`

### 3. Crie a chave gratuita da Groq

- Acesse [console.groq.com/keys](https://console.groq.com/keys) e clique em Create API Key
- Guarde o valor como `GROQ_API_KEY`

Chaves ficam só no `.env` local e nos Secrets do GitHub. O `.env` já está no
`.gitignore`: nunca o commite nem cole chave em issue ou chat.

### 4. Defina o @ do canal

Em `config.yaml`, troque `branding.handle` (`"@canal"`) pelo @ real do canal. Ele fica
gravado no vídeo como marca d'água, então descobrir o placeholder depois de publicado
significa refazer os vídeos. Enquanto ele não for trocado, o log avisa a cada execução.

### 5. Crie o app no TikTok for Developers

- Acesse [developers.tiktok.com/apps](https://developers.tiktok.com/apps) e clique em Create app
- Adicione os produtos **Login Kit** e **Content Posting API**
- Nos escopos do app, confirme `user.info.basic` e `video.upload`. Para publicar direto
  pelo painel, adicione `video.publish` e ligue o **Direct Post** no Content Posting API
- Em Login Kit > Redirect URI, cadastre a URL do passo 2
- Anote `Client key` e `Client secret`

### 6. Conecte a conta do TikTok (uma única vez, na sua máquina)

```bash
python -m src.oauth_setup --sem-terminal
```

Nada é colado no terminal: o script lê a área de transferência. Na página do app,
revele o `Client key` e o `Client secret` do passo 5 (ícone de olho), selecione os dois e
copie; o script separa um do outro sozinho. Ele abre o navegador para você autorizar com
a conta que vai postar; na página de retorno, selecione o `code` e copie. As chaves vão
direto para o `.env` e, com o `GH_PAT` do passo 7 já configurado, também para os Secrets
do GitHub. Nenhum token aparece na tela, e a área de transferência é limpa no fim.

Sem o `--sem-terminal`, o script pede um Enter depois de cada cópia. Colar a chave no
terminal não é usado de propósito: em vários terminais do Windows a colagem chega vazia
ou com caracteres invisíveis, e a plataforma recusa a chave.

O endereço de retorno é deduzido do repositório
(`https://SEU-USUARIO.github.io/SEU-REPO/oauth-callback.html`) e as permissões seguem o
`tiktok.mode` do `config.yaml`: só `video.upload` no modo upload, mais `video.publish` no
modo direto. `TIKTOK_REDIRECT_URI` e `TIKTOK_SCOPES` no ambiente trocam os dois.

### 7. Crie o token do GitHub (GH_PAT)

Com ele, o bot grava as chaves nos Secrets do repositório: tanto as dos passos de
conexão quanto o `refresh_token` do TikTok, que muda a cada renovação e invalida o
valor antigo na hora. O do YouTube não precisa disso, porque o Google não o rotaciona.

```bash
python -m src.push_secrets
```

Sem `GH_PAT` no `.env`, o comando abre a página de criação do GitHub com o escopo `repo`
já marcado. Escolha uma validade longa, gere o token e cole no terminal: ele vai para o
`.env` e as chaves que já existirem seguem para os Secrets.

### 8. Crie o projeto no Google Cloud e o app do YouTube

- Acesse [console.cloud.google.com](https://console.cloud.google.com/) e crie um projeto novo
- Em APIs e serviços > Biblioteca, ative **"YouTube Data API v3"**
- Em APIs e serviços > Tela de consentimento OAuth:
  - Tipo de usuário: **External**
  - Escopo adicionado: `https://www.googleapis.com/auth/youtube.upload`
  - Publique o app (botão "Publish app", mudando de "Testing" para "In production").
    Isso é essencial: em "Testing" o refresh_token expira em 7 dias e o bot para de
    funcionar sozinho.
  - Como o escopo `youtube.upload` é sensível, o Google pode mostrar um aviso de "app
    não verificado" para quem faz login. Isso é normal para uso pessoal: basta clicar
    em Avançado > Acessar mesmo assim (você mesmo é quem loga).
- Em APIs e serviços > Credenciais > Criar credenciais > ID do cliente OAuth, escolha o
  tipo **"App para computador" (Desktop app)**
- Anote o `Client ID` e o `Client secret`

A capa customizada exige canal verificado por telefone
([youtube.com/verify](https://www.youtube.com/verify)). Sem isso o vídeo é publicado
normalmente, só sem a capa.

### 9. Conecte o canal do YouTube (uma única vez, na sua máquina)

```bash
python -m src.youtube_oauth_setup
```

O script pede para copiar (botão de copiar do Google Cloud) o `Client ID` e o
`Client secret` do passo 8, apertando Enter depois de cada um. Ele confere o formato
antes de seguir: o ID termina em `.apps.googleusercontent.com` e o secret começa com
`GOCSPX-`. Depois abre o navegador para você entrar com a conta do canal e grava as
chaves no `.env` e nos Secrets do GitHub, do mesmo jeito que o passo 6.

O Google mostra o Client secret uma vez só, na hora em que ele é criado. Se precisar
trocar (por exemplo, se ele vazar), crie outro na credencial e rode
`python -m src.push_secrets --novo-secret-youtube`: o script pega o secret novo pela
área de transferência, ignora o antigo e atualiza o `.env` e o GitHub. O acesso ao
canal continua valendo, sem precisar conectar de novo.

### 10. Confira os Secrets no repositório

Os horários automáticos leem as chaves dos Secrets do GitHub, não do `.env`. Os passos
6 e 9 já gravam lá quando o `GH_PAT` existe. Os Secrets saem do seu computador já
criptografados e o GitHub não mostra o valor para ninguém, só deixa substituir ou apagar.
Para trocar a chave da Groq, crie a nova no console, copie e rode
`python -m src.push_secrets --nova-groq`. Para mandar tudo de uma vez, rode:

```bash
python -m src.push_secrets
```

Ele grava estes 8 e avisa quais ainda faltam no `.env`:

| Secret | Origem |
|---|---|
| `GROQ_API_KEY` | passo 3 |
| `TIKTOK_CLIENT_KEY` | passo 6 |
| `TIKTOK_CLIENT_SECRET` | passo 6 |
| `TIKTOK_REFRESH_TOKEN` | passo 6 |
| `GH_PAT` | passo 7 |
| `YOUTUBE_CLIENT_ID` | passo 9 |
| `YOUTUBE_CLIENT_SECRET` | passo 9 |
| `YOUTUBE_REFRESH_TOKEN` | passo 9 |

Para usar apenas uma das duas plataformas, deixe as chaves da outra de fora e
desative-a em `config.yaml` (`tiktok.enabled: false` ou `youtube.enabled: false`).

### 11. Teste manualmente antes de deixar no automático

Em Actions > Daily AI video post > Run workflow, rode primeiro com `dry_run: true`
(gera o vídeo mas não publica em nenhuma plataforma) e confira o artifact `video-*`:
ele traz o `final.mp4`, a `thumbnail.jpg` e o `metadata.json`. Depois rode com
`dry_run: false` para publicar de verdade.

A partir daí, o cron roda sozinho às 06h, 12h e 20h de Brasília.

## Customização

Tudo abaixo fica em `config.yaml`.

| Opção | Efeito |
|---|---|
| `fase` | `crescimento` ou `monetizacao` (ver [Estratégia](#estratégia-em-duas-fases)) |
| `fases.<fase>.*` | Palavras, número de cenas, duração mínima e fechamento de cada fase |
| `branding.handle` / `branding.watermark_*` | @ do canal na marca d'água, opacidade e quantas vezes ela aparece |
| `niche` | Define o universo das histórias |
| `script.topics` | Lista de temas, um por publicação |
| `script.hooks` / `script.arcs` | Estilos de gancho e estruturas narrativas em rotação. `script.ganchos_desativados` guarda o que saiu da rotação e o motivo |
| `script.extra_rules` | Regras de conteúdo coladas no prompt do roteiro |
| `script.model` | Modelo da Groq usado no roteiro. Confira a [página de modelos](https://console.groq.com/docs/models) antes de trocar, porque modelos são descontinuados periodicamente |
| `scenes.style` | Sufixo de estilo de todas as imagens: é o que dá unidade visual ao vídeo |
| `tts_voice` / `tts_rate` | Voz e velocidade da narração. Rode `edge-tts --list-voices` para ver as vozes |
| `video.zoom_effect` / `video.crossfade_seconds` / `video.color_boost` | Movimento de câmera, duração da transição e realce de cor |
| `captions.words_per_chunk` / `captions.bottom_margin` | Palavras por vez na legenda e distância até a base do vídeo. O padrão (420 px) mantém o texto acima da interface do TikTok |
| `thumbnail.enabled` | Liga ou desliga a capa |
| `sfx.music_enabled` / `sfx.music_volume` | Trilha de fundo sorteada de `assets/music/` (Mixkit, licença livre). Adicione seus próprios mp3 nessa pasta para variar |
| `hashtags_extra` | Hashtags fixas do canal, que entram primeiro em todo vídeo |
| `hashtags_max` | Total de hashtags por vídeo (4): as fixas mais a do personagem ou tema da história |
| `posting_hours_utc` | Horários de publicação em UTC. Precisa casar com os `cron` de `.github/workflows/daily-post.yml` |
| `tiktok.mode` / `tiktok.privacy_level` | Modo de publicação no TikTok (ver [Publicação](#publicação-no-tiktok)) |
| `youtube.privacy_status` | `public`, `unlisted` ou `private` |
| `content_mode` | `cenas` (padrão) ou `personagem`, o formato antigo de monólogo com personagem fixo (gerado com `python -m src.generate_character`) |

## Painel local

Para acompanhar a geração e publicar com um clique, sem terminal:

```bash
python painel.py
```

No Windows, também dá para abrir com dois cliques em `painel.bat`. O painel abre no
navegador e mostra:

+ **Novo vídeo:** o tema da vez, qualquer outro da lista ou um escrito na hora, com o
  gancho e o arco que vão ser usados
+ **Geração ao vivo:** as cinco etapas, cada imagem de cena aparecendo assim que fica
  pronta e o log completo
+ **Conferência:** o vídeo no player, a capa, a passagem declarada e a legenda pronta
  para copiar
+ **Publicação:** TikTok, YouTube ou os dois, sempre com confirmação antes de enviar. No
  TikTok, dá para mandar para o app do celular ou publicar direto no perfil, pela tela que
  a revisão do TikTok exige (veja [Publicação no TikTok](#publicação-no-tiktok))
+ **Histórico:** todos os vídeos gerados, com o que já saiu em cada plataforma

O painel roda só na sua máquina (endereço `127.0.0.1`, inacessível de fora) e usa as
chaves do `.env`, que nunca aparecem na página. A geração é o mesmo `main.py` do GitHub
Actions, então o vídeo sai igual ao da publicação automática. Se o TikTok renovar o
token durante uma publicação, o valor novo é gravado no `.env` e, com `GH_PAT`
configurado, também nos Secrets do repositório.

O tema da vez é o mesmo que a publicação automática daquele horário vai usar. Se for
publicar pelo painel e pelo agendamento no mesmo dia, escolha outro tema na lista.

## Rodando localmente

```bash
cp .env.example .env   # preencha os valores
pip install -r requirements.txt
set -a; . <(tr -d '\r' < .env); set +a
DRY_RUN=true python main.py
```

O `tr -d '\r'` remove a quebra de linha do Windows, que de outro jeito entra grudada no
valor de cada chave. No PowerShell:

```powershell
Copy-Item .env.example .env   # preencha os valores
pip install -r requirements.txt
Get-Content .env | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item "env:$k" $v }
$env:DRY_RUN = "true"; python main.py
```

O vídeo fica em `output/<data>_<publicação>/`, junto com a capa e o `metadata.json`.
Para publicar depois um vídeo já gerado, sem gerar outro:

```bash
python main.py --publicar output/2026-09-18_2 --plataformas youtube
```

Para testar só a montagem (imagens, narração, legendas, trilha e capa) com um roteiro
fixo, sem chamar a Groq e sem publicar nada:

```bash
python test_pipeline.py
```

## Estrutura do projeto

| Arquivo | Papel |
|---|---|
| `main.py` | Orquestra o pipeline e a publicação |
| `painel.py` / `web/painel.html` | Painel local: geração ao vivo, conferência e publicação |
| `src/script_gen.py` | Prompt, rotações e validação do roteiro |
| `src/images.py` / `src/scenes.py` | Imagem de cada cena e linha do tempo da narração |
| `src/tts.py` / `src/captions.py` | Narração com timing por palavra e legendas |
| `src/video.py` / `src/thumbnail.py` | Montagem do vídeo e da capa |
| `src/tiktok_api.py` / `src/youtube_api.py` | Publicação nas duas plataformas |
| `src/tiktok_token.py` | Guarda o token renovado do TikTok no `.env` e nos Secrets |
| `revisao_tiktok.md` | Textos da revisão do app no TikTok e roteiro do vídeo de demonstração |
| `src/oauth_setup.py` / `src/youtube_oauth_setup.py` | Conexão das contas (roda uma única vez), gravando as chaves no `.env` e nos Secrets |
| `src/push_secrets.py` | Manda as chaves do `.env` para os Secrets do GitHub |
| `src/github_secrets.py` | Salva o token renovado do TikTok nos Secrets do repositório |
