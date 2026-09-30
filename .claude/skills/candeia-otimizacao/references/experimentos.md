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
- Não há coleta de métrica. Enquanto não houver, melhoria de roteiro e de
  estrutura não tem como ser justificada pela regra de evidência.

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
