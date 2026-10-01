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
- O vídeo inteiro mede **−20,8 LUFS** integrado. YouTube e TikTok normalizam
  para cerca de −14, então a plataforma sobe o áudio ~7 dB, e a trilha sobe
  junto. Pode ser parte do que se percebe como "música alta".
- A faixa dinâmica medida é **LRA 2,0 LU**, bem comprimida para narração com
  trilha por baixo.

### Instrumentação (pré-requisito de quase tudo)
- **Meio pronto.** `src/analytics.py` coleta e `scripts/relatorio_desempenho.py`
  compara por gancho, arco e fase. Falta UMA coisa, e só o dono da conta pode
  fazer: refazer a autorização do Google para conceder
  `yt-analytics.readonly`, com `python -m src.youtube_oauth_setup`. O escopo já
  está no setup; o escopo de upload foi deixado intocado de propósito.
- **A amostra ainda não compara.** 14 vídeos publicados, espalhados em 5 tipos
  de gancho (1 a 4 por tipo) e 7 arcos (1 a 3 por arco). Mesmo com métrica na
  mão, diferença entre grupos desse tamanho é variação normal de alcance, não
  efeito do roteiro. O relatório avisa "amostra pequena" abaixo de 5 por grupo.
  Antes de comparar ganchos, o canal precisa publicar mais, ou concentrar em
  menos variantes de propósito.

## Experimentos concluídos

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
- **Decisão:** mantido. Falta confirmar de ouvido.

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

### Experimento proposto (não executado: depende de decisão do dono)

Concentrar em DOIS ganchos alternados, `convite` contra `final-primeiro`, em
vez de sortear entre cinco. Com 3 publicações por dia, dá ~15 de cada em 10
dias, que é onde a diferença passa a significar algo.

- **Medida:** % assistido médio por gancho
- **Critério de fracasso:** diferença menor que 8 pontos entre os dois grupos
  ao fim dos 10 dias significa que o gancho não é a alavanca, e a busca volta
  para outra variável (tema, primeira frase, duração)
- **Custo:** reduzir variedade por 10 dias. É mudança de identidade, e por isso
  não se faz sem o dono decidir.
