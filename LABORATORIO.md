# Laboratório do Candeia Bíblica

Espaço para testar melhorias sem parar o canal. O `main` continua publicando
todo dia; aqui a gente muda uma coisa por vez, mede e só depois leva para lá.

**Regra de ouro:** uma mudança por vez. Duas juntas e não dá para saber qual
funcionou. Cada teste tem hipótese, o que muda, o número que decide e quanto
tempo roda antes de concluir.

## Onde o canal está (20/09/2026)

| Número | Valor | O que diz |
|---|---|---|
| Visualizações do melhor vídeo | 422 | o YouTube distribui o formato |
| Inscritos vindos dele | 4 | quem assiste até o fim se inscreve |
| Duração média assistida | 0:11 de 0:36 | 31% do vídeo |
| **Continuaram assistindo** | **7,6%** | **92,4% pulam nos primeiros segundos** |

O gargalo é o começo do vídeo, não o meio. Todo teste da lista ataca isso
primeiro.

## O que funciona no nicho (pesquisa, 2026)

- **A decisão acontece entre 1 e 3 segundos.** O espectador decide ficar ou
  rolar antes da segunda frase. ([vidIQ](https://vidiq.com/blog/post/viral-video-hooks-youtube-shorts/), [Kineclip](https://kineclip.com/blog/how-to-write-viral-hooks-short-form-2026/))
- **Texto na tela no primeiro quadro**, de 3 a 7 palavras, grande, no terço
  superior, onde não briga com a interface do app. ([Miraflow](https://miraflow.ai/blog/how-to-go-viral-2026-what-actually-works-across-platforms))
- **Gancho de contradição ou lacuna de curiosidade** rende mais que anúncio do
  tema: uma frase que contraria o senso comum cria tensão que pede resposta.
  ([HookLayer](https://hooklayer.dev/guides/viral-hooks))
- **Re-ganchos a cada 10 a 15 segundos** seguram quem começou a dispersar. O
  algoritmo premia mais os 45 segundos seguintes do que os 3 primeiros.
  ([Shortzly](https://shortzly.com/blog/short-form-video-retention-strategies))
- **História bíblica sem rosto está em alta**, com produção por IA, e é nicho
  pouco disputado em português. ([FrontGate Media](https://www.frontgatemedia.com/christian-influencers-youtube-2026/))
- **Conteúdo cristão tem compartilhamento acima da média** para o mesmo número
  de views: emoção e devocional curto circulam mais que explicação.
  ([FrontGate Media](https://www.frontgatemedia.com/christian-brands-grow-youtube-2026/), [Social Growth Engineers](https://www.socialgrowthengineers.com/religion-faith-june-2026-social-growth-guide))
- **Quem cresce está em mais de uma plataforma ao mesmo tempo.** Reforça a
  prioridade de destravar o TikTok.

## Lista de testes

Ordem por impacto esperado dividido pelo esforço. Um por vez, sempre.

| # | Teste | Hipótese | O que muda | Número que decide | Tempo |
|---|---|---|---|---|---|
| 1 | Primeira frase sem desfecho | Contar o fim na abertura tira o motivo de ficar | Regra no prompt: nada de desfecho, palavra simples, pergunta implícita | "continuaram assistindo" sobe de 7,6% | 9 vídeos (3 dias) |
| 2 | Frase na tela nos 2 primeiros segundos | Texto grande segura o dedo de quem rola | Sobrepor a frase da capa no início do vídeo | idem, comparado com o teste 1 | 9 vídeos |
| 3 | Título com nome e conflito | "Quando o luxo encontra a pobreza" não diz quem nem o quê | Regra no prompt do título | cliques vindos de páginas de canal e busca | 2 semanas |
| 4 | Re-gancho no meio | Pergunta curta no meio segura quem ia sair | Prompt pede uma frase de tensão na cena do meio | duração média assistida | 9 vídeos |
| 5 | Vídeo de 1 minuto contra 35 segundos | Vídeo curto pode estar cortando a história | Trocar a fase para monetização | duração média e visualizações | 2 semanas |
| 6 | Voz feminina | A voz masculina grave pode não ser a melhor para o nicho | `tts_voice` para uma voz feminina pt-BR | continuaram assistindo | 9 vídeos |
| 7 | Estilo de imagem | Pintura a óleo pode cansar; testar cinematográfico realista | `scenes.style` | duração média | 9 vídeos |
| 8 | Trilha sonora | Trilha errada atrapalha a narração | trocar a música e o volume | duração média | 9 vídeos |
| 9 | Horários | 06h/12h/20h é palpite, não medição | mover um horário por vez | visualizações nas primeiras 2 horas | 2 semanas |
| 10 | Série numerada | "Parte 1 de 3" cria retorno | prompt e título em série | inscritos por vídeo | 2 semanas |

## Como medir sem se enganar

- O `metadata.json` de cada vídeo já guarda **gancho**, **arco**, **tema** e
  **fase**. Depois de algumas semanas dá para cruzar isso com a retenção do
  YouTube Studio e ver qual gancho ganha.
- A curva de retenção leva até 2 dias para aparecer. Não conclua antes disso.
- Compare sempre com a mediana dos últimos 9 vídeos, nunca com um vídeo só:
  um vídeo sozinho varia demais.
- Anote o resultado de cada teste aqui embaixo, com a data.

## Resultados

| Data | Teste | Antes | Depois | Decisão |
|---|---|---|---|---|
| | | | | |

## Como levar para o projeto

O laboratório vive no branch `laboratorio`. Quando um teste ganhar, abre-se uma
PR desse branch para o `main` só com a mudança que venceu, e o resto continua
em teste.
