# Registro de experimentos

Um experimento por entrada. Sem resultado escrito, o experimento não terminou
— e experimento que não terminou não pode virar evidência para o próximo.

## Formato

```
### [data] nome curto
- **Hipótese:** o que se acredita e por quê (com a evidência que motivou)
- **Mudança:** exatamente o que mudou, em qual arquivo
- **Medida:** o número que decide, e onde ele é lido
- **Critério de fracasso:** escrito ANTES, senão qualquer resultado vira vitória
- **Amostra:** quantos vídeos, em quanto tempo
- **Resultado:** o número que saiu
- **Decisão:** mantido, revertido, ou inconclusivo
```

## Hipóteses registradas e não testadas

Ficam aqui até existir dado para testá-las. Não implemente sem medir.

### Áudio (congelado — só registro, ver SKILL.md)

A hipótese do nível de entrega que estava aqui **foi confirmada e corrigida em
2026-10-02**, com autorização explícita do dono. Ver "nível de entrega e ganhos
medidos" nos concluídos. O resto do áudio (voz, TTS, velocidade, pitch,
sincronia) continua congelado.

- A faixa dinâmica agora mede **LRA 1,9 LU**, estreita. É consequência de pôr
  trilha e efeitos longe da voz, e é o normal para narração em formato curto.
  Se algum dia soar "chapado", a conversa é sobre dinâmica (compressão da voz,
  trilha com mais variação), e é escolha estética, não defeito.

### Instrumentação (pré-requisito de quase tudo)
- **Pronto desde 2026-10-01.** `src/analytics.py` coleta e
  `scripts/relatorio_desempenho.py` compara por gancho, arco e fase. A
  autorização com `yt-analytics.readonly` foi refeita e a YouTube Analytics API
  foi ativada no projeto do Google Cloud (ela é separada da Data API v3, e foi
  isso que travou a primeira tentativa). O escopo de upload continua intocado.
- **A amostra ainda não compara.** 14 vídeos publicados, espalhados em 5 tipos
  de gancho (1 a 4 por tipo) e 7 arcos (1 a 3 por arco). Mesmo com métrica na
  mão, diferença entre grupos desse tamanho é variação normal de alcance, não
  efeito do roteiro. O relatório avisa "amostra pequena" abaixo de 5 por grupo.
  Antes de comparar ganchos, o canal precisa publicar mais, ou concentrar em
  menos variantes de propósito.

### Estrutura do roteiro: número de cenas

**Cuidado ao ler isto: a faixa que vale é a da FASE ATIVA.** O `config.yaml`
tem dois blocos, e só um está em uso. Hoje `fase: crescimento`, que pede **6 a
9 cenas**. O `min_scenes: 8` que aparece no arquivo é da fase `monetizacao`,
que **não está ativa**. Comparar o roteiro com o número errado leva a concluir
defeito onde não há (aconteceu em 2026-10-01, ao conferir um vídeo de teste de
7 cenas: parecia abaixo do mínimo, estava dentro da faixa).

**O que as 30 execuções de produção desde 2026-09-18 mostram** (quando a fase
`crescimento` entrou):

| cenas | execuções | |
|---|---|---|
| 5 | 9 | abaixo do mínimo |
| 6 | 12 | dentro |
| 7 | 8 | dentro |
| 9 | 1 | dentro |

- **70% dentro da faixa, 30% abaixo**, nenhuma acima do máximo.
- **29 das 30 ficaram entre 5 e 7**, o fundo da faixa. A metade de cima (8 e 9)
  aconteceu **uma vez**.

Daí saem duas coisas diferentes, e vale não confundir:

1. **Um defeito pequeno e real:** o mínimo não é validado. Ele só entra no
   TEXTO do prompt (`src/script_gen.py:153`) e nada confere o JSON que volta,
   então 9 vídeos saíram com 5 cenas sem ninguém saber. Já existe laço de
   repetição para JSON inválido; pedir de novo quando vier abaixo da faixa é
   barato.
2. **Território não explorado:** o modelo encosta no fundo de qualquer faixa
   que recebe. Com duração quase fixa, número de cenas é ritmo de corte (6
   cenas em 50s dão planos de ~8s; 10 dariam ~5s), e **o canal praticamente
   nunca publicou um vídeo de corte rápido**. Não é que o corte rápido tenha
   sido testado e perdido: ele nunca existiu.

**O cruzamento com retenção NÃO sustenta nada.** Só 5 execuções têm ao mesmo
tempo `scenes/` em disco e `metricas.json` (`output/` é ignorado pelo git,
então pasta antiga some):

| cenas | n | assistido médio |
|---|---|---|
| 5 | 2 | 61,0% |
| 6 | 2 | 48,7% |
| 7 | 1 | 89,8% |

r = +0,51 com n=5, e o grupo de 7 cenas é UM vídeo: o dos pastores, o mesmo
que já infla `convite` e `ultimo-vira-primeiro`. Terceira aparição da mesma
armadilha. Então a motivação aqui é **a faixa de cima nunca ter sido tentada**,
não um efeito medido.

**O experimento, quando chegar a vez (depois de 2026-10-11):** pedir 6–7 contra
10–12 cenas, alternando por publicação como no experimento dos ganchos, e
comparar % assistido com n≥15 de cada. Para o grupo alto existir de verdade,
primeiro precisa do item 1 acima: sem validar o retorno, o modelo devolve 7 e
os dois grupos viram o mesmo grupo.

**Critério de fracasso, escrito antes:** diferença menor que 8 pontos de %
assistido significa que número de cenas não é a alavanca.

**Não implementar agora:** o experimento dos ganchos corre até 2026-10-11, e
mexer em estrutura de roteiro no meio dele faria as duas mudanças se
confundirem.

**Como remedir:**

```bash
python - <<'EOF'
import glob, os, re, collections
dist = collections.Counter()
for d in sorted(glob.glob("output/*/")):
    nome = os.path.basename(d.rstrip("/\\"))
    if nome.startswith(("teste", "_test")):
        continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", nome)
    if not m or m.group(1) < "2026-09-18":
        continue
    n = len(glob.glob(os.path.join(d, "scenes", "*.png")))
    if n:
        dist[n] += 1
print(dict(sorted(dist.items())))
EOF
```

## Defeitos medidos e ainda não corrigidos

Não são hipóteses: foram contados em execuções reais. Ficam aqui porque a
correção depende de decisão do dono do canal, não de mais medição.

### Histórias de santo ganham episódio inventado

Das execuções com tema de santo fora da Bíblia, **3 de 3** inventaram
acontecimento concreto e verificável:

- Santa Teresinha (01/10): "começou a visitar crianças doentes, entregando-lhes
  a mesma flor". Era carmelita de clausura, entrou no convento aos 15 anos.
- Santa Dulce (`lote_2026-09-25_2`, publicado): "vendeu sua própria roupa e
  passou noites na rua, pedindo migalhas para comprar uma cama velha".
- Frei Galvão (`lote_2026-09-26_2`, publicado): a cena inteira do menino, do
  padeiro e das duas jarras de água. Frei Galvão é conhecido pelas pílulas de
  papel, não por jarras.

A regra existe (`extra_rules`: "Em história de santo, fique no que a tradicao
registra") e não está sendo cumprida. É o mesmo mecanismo que fez o gancho
`contraintuitivo` sair da rotação: o modelo entrega o que foi pedido às custas
da fidelidade.

**Por que isto NÃO é simples como o de cima:** não existe jeito determinístico
de saber se um episódio está na tradição. Os caminhos possíveis, nenhum testado:
dar a fonte junto do tema no prompt; restringir a narração a um resumo do que o
tema já afirma; tirar santo não-bíblico da rotação (28 temas de `personagem`,
16 de santo, e o slot do meio é 90% `personagem`, então isso mudaria um terço
das publicações); ou trocar o modelo para essas histórias. Decisão do dono do
canal, não da skill.

**Como remedir:** cruzar o campo `tema` de cada `metadata.json` com a lista
`script.topics.personagem` do `config.yaml` e ler a narração dos que são de
santo. Não há como automatizar o julgamento: alguém precisa saber o que a
tradição registra.

## Experimentos concluídos

### 2026-10-02 validador do fecho

Autorizado pelo dono depois de ver a medição.

**O defeito:** o prompt tinha regras "NUNCA" que o modelo ignorava, e nada
conferia. Medido sobre as 34 execuções com narração em disco:

| regra quebrada | execuções | onde a regra está |
|---|---|---|
| a última frase é pergunta | 9 (26%) | `src/script_gen.py`, regra 4 da abertura |
| chama o próximo vídeo | 4 (12%) | "nunca é fórmula vaga do tipo 'qual será o...'" |
| o TEXTO da instrução vazou para a narração | 2 (6%) | — |

11 das 34 (32%) com pelo menos uma. As duas do vazamento são as piores porque
o espectador **ouve a instrução**, e as duas foram publicadas:
"...aceitou o presente, **deixando o silêncio perguntar**: qual será a próxima
prova de fé?", quando a instrução diz "Termine deixando uma pergunta no ar,
SEM FAZER a pergunta".

**Por que não precisou de evidência nova:** a regra já era decisão do dono. O
que faltava era conferir se foi cumprida. Regra escrita e regra conferida são
coisas diferentes, e só a segunda vale.

**A mudança:** `regras_do_fecho_quebradas()` entra no laço de retentativa de
`generate_scene_script`, no mesmo formato dos quatro validadores que já
existiam (`hook_entrega_fim`, `cliche_na_narracao`, `warn_distant_words`,
`texto_corrompido`). Roteiro com o fecho errado é recusado e o modelo é
chamado de novo, até 3 vezes.

Três decisões que valem registro:

1. **Não trava a publicação.** Esgotadas as tentativas, segue com um AVISO no
   log. Fechar com pergunta é defeito de estilo; não publicar nada naquele
   horário é pior.
2. **Entre dois roteiros acima do mínimo de palavras, fica o de fecho limpo.**
   Antes a escolha era só por número de palavras, e isso publicaria o defeito
   por causa de 150 palavras a mais. Abaixo do mínimo continua vencendo o mais
   comprido, porque aí o risco é a monetização.
3. **Os padrões moram em `src/script_gen.py`**, e `scripts/conferir_roteiros.py`
   importa de lá. Duplicar criaria duas versões da mesma regra em arquivos
   diferentes, que é exatamente o bug das duas constantes de volume.

**Verificado:** reconhece os três defeitos nas frases reais que saíram
publicadas; recusa e devolve o roteiro limpo na segunda tentativa; com todas as
tentativas quebradas, segue avisando em vez de travar; e escolhe o fecho limpo
com 157 palavras em vez do quebrado com 306. O medidor dá os mesmos números de
antes (9/4/2), então o refactor não mudou a definição da regra.

### 2026-10-02 nível de entrega e ganhos medidos

Autorizado explicitamente pelo dono ("o áudio tá com chiado, a música tá alta").
Duas reclamações, uma raiz: **todo nível de áudio era constante cega.**

**O que estava errado, medido:**

| | medido | referência |
|---|---|---|
| entrega do vídeo | −25,4 LUFS | plataformas usam ~−14 |
| trilha vs voz | 13,3 dB abaixo (10,3 no pico) | locução sobre trilha: 15–20 |
| `fanfarra` (efeito de virada) vs voz | **0,6 dB ACIMA** | — |
| `tensao_riser`, `impacto` vs voz | 2,0 e 2,9 dB abaixo | — |
| ambientes vs voz | 10,3 a 17,5 dB abaixo | — |

O dono apontou dois instantes, e os dois bateram com a medição: **0:37** é o
início da última cena, onde o efeito de virada dispara (`main.py`, cue com
`volume: 0.22`); **0:04** é narração com ambiente por cima, e ruído de banda
larga a 11 dB da fala soa como voz chiando. Confirmado por eliminação: a voz
isolada, no mesmo nível de entrega, **não chia** (verificado de ouvido pelo
dono), então o problema era o que vinha somado por cima.

**Por que as correções anteriores falharam.** Duas tentativas baixaram números
absolutos (0.10 → 0.06, depois teto de 0.085) e a música continuou alta. Não
podiam funcionar: o que se ouve é a RELAÇÃO com a voz, e a voz também era
baixa. Pior, as fontes têm níveis muito diferentes entre si (7,7 dB entre as
trilhas, 25 dB entre os efeitos), então um ganho fixo produz resultados
diferentes conforme o sorteio do clima.

**O que mudou:** todo ganho passou a ser derivado de medição, contra a
narração como referência (`src/video.py`):

- trilha 22 dB abaixo da voz, efeito de virada 18 dB, ambiente 26 dB;
- a narração é medida por **loudness integrada (LUFS), não RMS médio**: o RMS
  inclui as pausas e variou 2,9 dB entre duas gerações (−26,1 e −29,0),
  enquanto o LUFS variou 0,85 dB em seis arquivos. Mede-se a mediana de até
  três cenas;
- o vídeo é normalizado para −16 LUFS com pico em −2,0 dBTP, depois do mix,
  copiando o vídeo sem recomprimir (`-c:v copy`);
- os valores no `config.yaml` e nos cues viraram reserva, usados só se a
  medição falhar.

**Resultado, no arquivo gerado:** −16,3 LUFS, pico −1,9 dBFS, flat factor 0
(sem clipagem), as sete trilhas e os dez efeitos todos no mesmo lugar em
relação à voz. `fanfarra` de ganho 0,22 para 0,026, 18,5 dB mais baixa.

**Decisão:** falta confirmação de ouvido do dono.

**Armadilha que isto deixou registrada:** normalizar para cima levanta tudo
junto, inclusive a música. Por isso o alvo é −16 e não −14, e a trilha foi para
22 dB (não 18): o resultado é música mais baixa em termos absolutos do que
antes, com a voz 9 dB acima. Mexer no alvo de loudness sem mexer na relação
devolve o problema.

### 2026-09-30 acentuação do prompt
- **Hipótese:** a narração pronunciava "istória" porque o texto chegava ao TTS
  sem acento; o prompt em `config.yaml` tinha 32.945 caracteres e **6**
  acentuados, incluindo o exemplo de gancho "Vamos ouvir uma historia de Deus?"
  que o modelo copia literalmente.
- **Mudança:** 210 palavras acentuadas em `config.yaml`, só as que nunca
  existem sem acento. `esta/está` e `e/é` ficaram de fora porque mudam de
  sentido e exigem ler a frase.
- **Medida:** pronúncia na narração gerada; contagem de acentos no prompt.
- **Resultado:** 6 → 214 caracteres acentuados. Estrutura do YAML conferida:
  143 chaves idênticas, zero valores não-texto alterados.
- **Decisão:** mantido. Falta confirmar de ouvido no próximo vídeo gerado.

### 2026-09-30 teto da trilha
- **Hipótese:** a música voltou a soar alta porque `SWELL_PEAK` (2.2) desfazia
  a redução anterior do volume base: `0.06 × 2.2 = 0.132`, acima dos `0.10`
  que já haviam sido reclamados.
- **Mudança:** `TETO_DA_TRILHA = 0.085` em `src/video.py`, cortando o pico
  independentemente do volume base.
- **Resultado:** pico de `0.132` para `0.085`.
- **Decisão:** **FALHOU, e foi substituído em 2026-10-02.** Confirmado de
  ouvido pelo dono: a música continuou alta. O teto não podia resolver, porque
  o que se ouve é a relação com a voz, e a voz também era baixa. O teto virou
  só rede de segurança (ver "nível de entrega e ganhos medidos"). Lição: medir
  o lado que se mexeu e não o que se quer ouvir é meio diagnóstico.

## Linha de base (2026-10-01)

A primeira medição real do canal. Tudo daqui para frente se compara com isto.

**Canal:** 14 vídeos publicados, 13 com dado no Analytics, **2.582 views**,
**62% assistido** em média.

| gancho | vídeos | assistido | views |
|---|---|---|---|
| convite | 1 | 90% | 511 |
| meio-da-acao | 4 | 68% | 379 |
| pergunta | 3 | 63% | 480 |
| detalhe-estranho | 2 | 55% | 250 |
| final-primeiro | 4 | 51% | 962 |

Melhor vídeo isolado: `BgiXou6SXrQ`, 89,8% assistido e 43s médios, mais que o
dobro da duração média do canal.

### O que isto NÃO prova, e por quê

A leitura óbvia ("convite é o melhor gancho") é armadilha: é **um** vídeo. Com
n=1 não há como separar o gancho do tema, do horário ou de sorte do algoritmo.

Pior: os dois vídeos dos pastores aparecem ao mesmo tempo em `convite`, em
`ultimo-vira-primeiro` e no topo da lista individual. Um vídeo bom infla três
categorias e **parece três evidências**. Ao ler este relatório, confira se o
grupo que parece vencer não é o mesmo vídeo contado de novo.

O único sinal que merece ser olhado de novo quando houver amostra:
`final-primeiro` tem a **maior audiência e a pior retenção** (962 views, 51%),
o padrão de um gancho que atrai o clique e não segura. Com 4 vídeos ainda cabe
na variação normal.

## Experimento 1: concentrar a rotação em dois ganchos

**Estado:** em andamento. Autorizado pelo dono do canal em 2026-10-01, decidir
em 2026-10-11.

**Pergunta:** o estilo de abertura muda a retenção?

**Por que concentrar:** com cinco ganchos e três publicações por dia, cada um
sai umas 6 vezes por mês. Seis amostras não separam 55% de 68%, porque o tema
e a miniatura mexem mais que isso nessa escala. Dois ganchos alternados dão
~15 vídeos de cada em 10 dias, e aí a diferença passa a significar algo.

**Mudança:** campo novo `script.ganchos_concentrados` no `config.yaml`, lido
por `script_gen.ganchos_em_rotacao()`. Lista com nomes = só eles giram; lista
vazia = voltam os cinco. Nenhuma instrução foi apagada ou movida: as cinco
continuam inteiras em `script.hooks`.

**Os dois escolhidos, e a correção do par proposto antes:**

A proposta original era `convite` contra `final-primeiro`. Isso estava errado,
e o erro veio de ler uma versão desatualizada do `config.yaml`:
**`final-primeiro` já tinha saído da rotação em 20/09/2026, com dado** (o
vídeo de 422 views que usou esse gancho teve 92,4% de saída nos primeiros
segundos). Reativá-lo seria desfazer uma decisão que já foi tomada com
evidência, para medir de novo o que já se mediu. Os 51% dele na linha de base
são de vídeos anteriores a essa data.

O par executado é:

| papel | gancho | o que se sabe |
|---|---|---|
| controle | `meio-da-acao` | padrão de fato do canal: 20 dos 50 vídeos publicados, 68% assistido com n=4. É o número mais confiável que existe aqui. |
| desafiante | `convite` | dono do melhor vídeo do canal (89,8% assistido), mas com n=1. |

Comparar contra o incumbente é o que torna o resultado acionável: se `convite`
ganhar, ele vira o padrão. Comparar contra o pior gancho só produziria um
vencedor que já se esperava.

**Medida:** % assistido médio por gancho, de `scripts/relatorio_desempenho.py`.

**Critério de fracasso, escrito ANTES de ver o resultado:** diferença menor que
8 pontos de % assistido ao fim dos 10 dias significa que o gancho **não** é a
alavanca, e a busca passa para outra variável (tema, primeira frase, duração).
Diferença maior: o perdedor sai da rotação.

**Verificado antes de publicar** (simulação dos 10 dias com o `config.yaml`
real, pelas funções reais):

- 15 publicações de cada gancho em 10 dias, exatamente
- 5 de cada em cada um dos três horários (9h, 15h e 23h UTC), então o horário
  não favorece nenhum dos dois
- todos os 14 pares gancho+arco aparecem, então nenhum dos dois fica preso a
  um tipo de história
- a instrução de cada gancho chega literal ao prompt do roteiro
- lista vazia, campo ausente ou nome errado na lista: os cinco voltam a girar

**Custo aceito:** 10 dias com menos variedade de abertura, e `fato-chocante`
(pedido do dono em 23/09/2026) espera a vez para ser medido.

**Armadilha para a leitura do resultado:** 15 vídeos por grupo ainda é pouco
para diferença pequena. O critério de 8 pontos existe para não transformar
ruído em decisão. E vale a conferência do costume: se um grupo vencer, veja se
não é um vídeo bom contado várias vezes.
