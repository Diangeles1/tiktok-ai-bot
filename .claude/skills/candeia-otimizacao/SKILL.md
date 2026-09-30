---
name: candeia-otimizacao
description: Rotina de melhoria contínua do canal Candeia Bíblica (D:\tiktokbot) — o bot que gera e publica Shorts bíblicos em português. Use sempre que a conversa for sobre melhorar os vídeos do canal, desempenho, retenção, gancho, roteiro, capa, ritmo, "por que esse vídeo não foi bem", "o que dá pra melhorar", ou qualquer mudança no gerador de vídeos. Use também antes de editar config.yaml, src/script_gen.py, src/video.py ou src/images.py, porque este projeto tem armadilhas que já quebraram a produção. O áudio é congelado: se a conversa for sobre voz, TTS, volume ou trilha, esta skill diz o que fazer.
---

# Candeia Bíblica: melhorar sem quebrar

Este canal já funciona. Ele gera e publica sozinho, 3x por dia. O trabalho
aqui **não** é reconstruir nem redesenhar: é fazer o canal melhorar aos poucos
sem perder o que ele já é, e sem derrubar a produção.

Duas coisas tornam isso difícil, e as duas são o motivo desta skill existir:

1. É muito fácil "melhorar" no escuro. Sem dado, toda mudança é palpite com
   cara de decisão, e palpite acumulado destrói a identidade do canal.
2. Este repositório tem armadilhas que já causaram bugs reais em produção.
   Elas não são óbvias e não aparecem em teste: aparecem no vídeo publicado.

## A regra que vem antes de todas

**Nenhuma mudança relevante sem evidência.** Evidência é uma destas:

- dados reais dos vídeos já publicados;
- dados do YouTube Studio ou da API;
- documentação oficial do YouTube;
- experimento anterior deste próprio canal, registrado;
- padrão consistente observado em vários vídeos (não em um).

Opinião de terceiro não é evidência. "Parece melhor" não é evidência. A
tentação aqui é real e vale nomear: quando alguém pede para melhorar, a coisa
mais natural do mundo é mexer em algo e entregar. Resistir a isso é o trabalho.

**O que fazer quando não há evidência:** dizer isso, com todas as letras, e
propor como obtê-la. Não invente uma justificativa plausível para uma mudança
que você quer fazer. Um "não tenho como saber ainda" honesto vale mais que uma
mudança bem argumentada e sem base — porque a mudança sem base vai ser seguida
por outra, e daqui a dez o canal virou outra coisa sem ninguém ter decidido.

### O estado real hoje: não há dados

Leia isto antes de prometer qualquer análise de desempenho.

O projeto **não coleta métrica nenhuma**. Não existe módulo que leia YouTube
Analytics; `src/youtube_api.py` só publica. Há poucos vídeos publicados em
`output/auto_*/`, e o que se guarda deles é `metadata.json` (tema, narração,
título) — nada de views, retenção ou conclusão.

Isso significa que, hoje, quase toda melhoria de roteiro ou estrutura cai na
regra acima e **não pode ser feita**. Confirme o estado antes de concluir:

```bash
ls -d output/auto_* | wc -l          # quantos vídeos existem
grep -rl "analytics\|retention" src/  # vazio = ainda sem coleta
```

Então o primeiro experimento útil deste canal quase certamente é
**instrumentar**: puxar da YouTube Analytics API, por vídeo, as visualizações,
a duração média assistida, a porcentagem assistida e a curva de retenção,
guardando ao lado do `metadata.json` que já existe. O OAuth já está montado
para publicar, então o caminho é curto.

Sem isso, o que sobra de honesto é: arrumar defeito relatado pelo usuário,
arrumar bug medido, e registrar hipóteses para testar quando houver dado.

## O áudio está congelado

Não altere voz, narração, velocidade, pitch, volume, trilha, efeitos, mixagem,
sincronia, arquivos de áudio, TTS nem processamento de voz — **mesmo achando
que melhoraria a retenção**. Registre a hipótese em
`references/experimentos.md` e siga.

A exceção é estreita e precisa ser explícita: o usuário pediu aquela mudança
de áudio, nesta conversa, descrevendo o defeito. Reclamação dele ("a música
está alta") é autorização para corrigir **aquilo**, não para revisar a
mixagem. Ao fazer, diga o que tocou e o que não tocou.

O texto que o TTS **lê** não é o sistema de áudio: melhorar o roteiro é
permitido, e acentuação correta é roteiro (ver armadilhas). Mudar a voz que lê
o texto não é.

## A identidade não se negocia

Preservar: identidade visual, estilo narrativo, temática, formato, o jeito de
falar, a estrutura geral, a sensação de marca. As melhorias são evolutivas.
Se uma proposta faria um espectador habitual pensar "mudou de canal", ela está
errada mesmo que os números melhorassem.

## O que pode melhorar

**Roteiro:** força dos primeiros segundos, clareza da história, velocidade,
corte do que não serve, curiosidade, progressão, payoff, final, motivo para
reassistir.

**Visual:** qualidade e consistência das imagens, composição, enquadramento,
movimento, transições, ritmo, sincronia entre imagem e narrativa, variedade de
cenas, legibilidade em tela de celular.

**Edição:** duração das cenas, timing dos cortes, entrada e saída de
elementos, intensidade, eliminação de tempo morto, sincronia visual com os
momentos importantes.

**Estrutura**, que é onde as perguntas ficam mais concretas:

| trecho | a pergunta |
|---|---|
| 0–1s | Começa imediatamente? Existe motivo para não deslizar? |
| 1–3s | A história já está clara? Há pergunta ou situação que gera curiosidade? |
| 3–10s | A narrativa avança, ou repete o que já foi dito? |
| meio | Cai o interesse? Há repetição? |
| final | Existe payoff? O final satisfaz? Dá vontade de ver de novo? |

Use essas perguntas assistindo ao vídeo, não lendo o código.

## Um experimento por vez

Mudança grande e mudança composta não ensinam nada: quando o número mexe,
ninguém sabe qual parte foi. Então:

- uma variável por vez;
- declarada antes: o que muda, o que se espera, como se mede, em quantos vídeos;
- registrada em `references/experimentos.md`, com o resultado depois;
- revertida sem drama se não funcionar.

Um experimento sem critério de fracasso escrito antes não é experimento.

## Como mexer neste repositório sem quebrá-lo

Leia `references/armadilhas.md` **antes da primeira edição** em `config.yaml`,
`src/video.py`, `src/script_gen.py` ou `src/images.py`. São quatro armadilhas
que já causaram bugs reais aqui, todas invisíveis no terminal.

As duas mais perigosas, em resumo, porque custam produção:

1. **O terminal é cp1252 e mente sobre acentos.** Texto correto aparece com
   `?`. Nunca conclua que há corrupção pelo que a tela mostra: confira os
   bytes. E nunca use `python -c` para texto em português — use heredoc com
   `encoding="utf-8"` explícito.

2. **Nunca altere CHAVES do `config.yaml`, só valores.** O código lê
   `cfg["video"]`; renomear a chave derruba a geração inteira. Depois de
   qualquer edição no arquivo, rode:

   ```bash
   python .claude/skills/candeia-otimizacao/scripts/conferir_config.py
   ```

   Ele compara a estrutura com a do último commit e falha se alguma chave ou
   algum valor não-texto mudou.

## Como se comporta uma boa sessão aqui

Comece entendendo o que a pessoa quer de verdade, e confira se existe dado
para sustentar. Se não existe, diga. Prefira corrigir um defeito concreto e
medido a propor três melhorias plausíveis. Meça antes de mexer: neste projeto,
a medição já contrariou a intuição várias vezes, e as correções que duraram
foram todas as que começaram com um número. Depois de mexer, confira que não
quebrou. E conte o que ficou por fazer.
