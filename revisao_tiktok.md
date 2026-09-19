# Revisão do app no TikTok

Textos para colar na ficha do app em TikTok for Developers (em inglês, que é o que a
equipe de revisão lê) e o roteiro do vídeo de demonstração.

## Description (máximo 120 caracteres)

```
Publish your original Bible-story videos to TikTok with a full preview, privacy choice and control over every post.
```

## Explain how each product and scope works (máximo 1000 caracteres)

```
Candeia Biblica is an open-source tool that creators run on their own computer to publish original Bible-story videos in Portuguese. The creator makes a video in our dashboard (AI-assisted script, images and narration), watches the full preview and only then publishes it to their own TikTok account.

Login Kit, user.info.basic: the creator connects their account once. We show their nickname and avatar so they know which account will receive the post.

Content Posting API, Direct Post, video.publish: the post screen calls creator_info. The creator edits the caption, picks who can view it (no default, only options from creator_info), turns on comments, duet or stitch (all off by default, locked if disabled in their settings), sets the commercial content disclosure and sees the Music Usage Confirmation notice. Nothing is posted until they click Publish. Posts are labeled as AI-generated.

video.upload: the creator can instead send the video to their TikTok inbox and finish it in the app.
```

## Vídeo de demonstração (o que gravar)

Grave a tela do computador. No Windows, Windows + Alt + R começa e para a gravação da
Xbox Game Bar, que grava só a janela que está na frente: deixe tudo no Chrome. Uma
gravação só, de 2 a 4 minutos, sem cortes:

1. **Conectar a conta.** Rode `python -m src.oauth_setup --sem-terminal`; quando o
   Chrome abrir a página do TikTok pedindo autorização, comece a gravar ali e clique em
   autorizar. Se a conta já estiver conectada com a permissão de publicar direto, pode
   pular e começar do passo 2.
2. **Abrir o painel** em http://127.0.0.1:8765 e clicar num vídeo pronto.
3. **Dar play no vídeo** por alguns segundos (a revisão quer ver a prévia).
4. **Na parte Publicar**, deixe o TikTok marcado e escolha "Publicar direto no perfil".
   Mostre com calma, passando o mouse por cima:
   - "Publicando como" com o nome e a foto da conta;
   - a legenda sendo editada (apague e escreva uma palavra);
   - "Quem pode ver" começando vazio, depois escolha **Somente eu** (enquanto o app
     não é aprovado, é a única opção que publica);
   - Comentários, Dueto e Costura desmarcados; marque Comentários;
   - ligue a Divulgação de conteúdo comercial, marque "Sua marca" e depois "Conteúdo de
     marca" (mostra o rótulo mudando e o "Somente eu" travando), e desligue de novo;
   - o aviso "Ao publicar, você concorda com a Confirmação de Uso de Música do TikTok".
5. **Clicar em Publicar**, confirmar na janela e esperar a mensagem de publicado, que
   avisa que o TikTok pode levar alguns minutos para processar.
6. **Abrir o seu perfil** em tiktok.com, no mesmo Chrome, e mostrar o vídeo publicado.

Antes de gravar:

- No TikTok for Developers, o **Direct Post** precisa estar ligado no Content Posting API
  do app, e a conta reconectada depois disso (o passo 1).
- Enquanto o app não é aprovado, o TikTok pode recusar a publicação direta em conta
  pública. Se aparecer o erro de "conta em modo privado", deixe a @candeiabiblica
  privada só durante a gravação (Perfil > menu > Configurações e privacidade >
  Privacidade > Conta privada) e volte para pública logo depois. Os vídeos publicados
  continuam lá.
- Se a ficha recusar o arquivo por tamanho, grave de novo em resolução menor (720p).
