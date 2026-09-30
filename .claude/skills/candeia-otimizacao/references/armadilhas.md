# Armadilhas deste repositório

Quatro armadilhas que já causaram bugs reais aqui. Nenhuma delas aparece em
teste, e três delas mentem no terminal. Leia antes da primeira edição.

## 1. O terminal é cp1252 e mente sobre acentos

O console deste Windows não é UTF-8. Texto em português **correto** aparece
com `?` ou `�` na tela. Isso levou a um diagnóstico errado nesta base: eu
"vi" `vers?culos` no metadata e concluí que os acentos estavam corrompidos.
Estavam intactos — o que estava errado era a exibição.

**Nunca conclua corrupção pelo que a tela mostra. Confira os bytes:**

```bash
python - <<'PY'
raw = open("arquivo.json", "rb").read()
i = raw.find(b"vers")
print(raw[i:i+16].hex(" "), "->", repr(raw[i:i+16]))
PY
```

`c3 ad` é UTF-8 correto para **í**. Se aparecer isso, o dado está bom.
Sinal real de corrupção é `U+FFFD` (`�`) no texto decodificado, ou
bytes cp1252 soltos (`ed` sozinho, sem o `c3` antes).

## 2. `python -c` corrompe texto em português

O argumento passa pela codificação do console e volta errado. Para qualquer
script que **leia ou escreva** texto pt-BR, use heredoc, e abra os arquivos
com `encoding="utf-8"` explícito:

```bash
python - <<'PY'
import io
t = io.open("config.yaml", encoding="utf-8").read()
io.open("config.yaml", "w", encoding="utf-8", newline="\n").write(t)
PY
```

Dentro do heredoc, escreva acento como escape (`é`) quando o texto for
crítico: sobrevive a qualquer camada intermediária.

## 3. Nunca altere CHAVES do `config.yaml`

O código lê `cfg["video"]`, `topics["reflexao"]`. Renomear a chave faz o
código parar de achar, e a falha aparece na geração, não na edição.

Isto já aconteceu: uma substituição de acentos no arquivo inteiro transformou
`video:` em `vídeo:` e levou junto as 11 chaves abaixo dela, mais
`script.topics.reflexao`. A geração teria quebrado inteira.

**A regra:** em linha de chave, só a parte **depois** dos dois-pontos pode ser
tocada. O padrão que identifica linha de chave:

```python
CHAVE = re.compile(r"^(\s*(?:-\s+)?[A-Za-z_][A-Za-z0-9_]*\s*:)(.*)$")
```

Linhas de bloco (`|`), itens de lista e comentários são valor: podem ser
editados inteiros.

**Depois de qualquer edição, confira:**

```bash
python .claude/skills/candeia-otimizacao/scripts/conferir_config.py
```

## 4. Constantes que se multiplicam entre arquivos

`sfx.music_volume` mora em `config.yaml`. `SWELL_PEAK` mora em `src/video.py`.
O volume que o espectador ouve é o **produto** dos dois.

Isto desfez uma correção sem ninguém perceber: depois de "a música está alta",
o volume base foi baixado de `0.10` para `0.06`. Mas `SWELL_PEAK = 2.2` levava
o pico para `0.132` — **mais alto que os `0.10` reclamados**. O defeito voltou
porque duas constantes em arquivos diferentes nunca foram multiplicadas juntas.

**Ao baixar um valor para corrigir algo, procure o que o multiplica:**

```bash
grep -rn "music_volume\|SWELL\|volumex\|\* *[A-Z_]\{3,\}" src/ config.yaml
```

E quando houver um teto que importa, escreva o teto, não o multiplicador:
`TETO_DA_TRILHA` em `src/video.py` corta o pico seja qual for o volume base,
o que torna essa regressão impossível de repetir.

## Coisas do canal que valem saber

- **Capa personalizada é rejeitada**: a conta do YouTube não tem verificação
  por telefone. Não gaste tempo melhorando thumbnail até isso mudar.
- **O agendamento do GitHub Actions atrasa de 2 a 5 horas.** Se a pergunta for
  "por que postou fora da hora", é isso, e não o código.
- **Cota da Cloudflare (imagens): 10 mil neurônios por dia.** Ela **não** volta
  em horário previsível — já prometi 00:00 UTC e estava errado. Nunca prometa
  horário. Existe reserva na Pollinations quando a cota acaba.
- **Cota da Groq: 200 mil tokens por dia**, ~3.600 por roteiro. Planeje
  experimento de roteiro sabendo disso.
