# Implementation Plan: Explicação de Indicadores v1 — causa provável por Epic (LLM)

> Spec: [SPEC-explicacao-de-indicadores.md](../../SPEC-explicacao-de-indicadores.md) (aprovada em 2026-11-11)
> Tarefas: [todo.md](todo.md)
> Status: **aprovado em 2026-11-11** · E1–E4 e checkpoints A/B concluídos; E5 e E6 concluídos — v1 liberada

## Overview

Um pacote `explicacao/` monta os fatos de cada Epic do Escalar a partir das linhas que o
Radar e o registro de riscos já produzem, anonimiza as pessoas, consulta um cache, chama a
OpenAI só no que falta, valida a resposta e devolve narrativas prontas. O `riscos.painel`
recebe as narrativas por parâmetro e as mostra no bloco Escalar.

## Architecture Decisions

- **Fatos a partir das linhas, não dos `Dados`.** As linhas do Radar (`radar-*.csv`) e do
  registro (`riscos-*.csv`) já têm tudo o que o LLM pode ver. Assim, a entrada do LLM é
  exatamente o que o painel mostra, e o validador compara contra esse texto.
- **Cliente HTTP isolado** (`explicacao/cliente_openai.py`, com `requests`) atrás de uma
  função `completar(sistema, usuario) -> Resposta`. Os testes injetam um cliente falso, e
  nenhum teste usa a rede. O nome `cliente_openai` evita confundir com o SDK `openai`.
- **`radar.narrativa.Narrador` fica como está.** Ele narra a linha do Radar, e o Radar
  continua com `NarradorNulo`. A narrativa de causa é outra peça: o orquestrador em
  `explicacao/narrativas.py` (ajuste registrado na spec).
- **Cache = os próprios `narrativas-*.csv`.** A chave é o hash do modelo, da versão do
  prompt e dos fatos anonimizados. Uma execução repetida não chama a API.
- **Anonimização por substituição de texto.** O nome do dono vira "Pessoa A" em todos os
  campos, inclusive no título, se aparecer lá. A troca de volta acontece só no HTML.
- **Falha nunca derruba o painel.** Exceções de rede, HTTP e JSON viram `status=erro`, com
  mensagem sem a chave.

## Dependency Graph

```
E1 fatos + anonimização
 └─ E2 prompt + validador
     └─ E3 cliente OpenAI + orquestrador (cache, CSV)
         └─ E4 painel (bloco Escalar) + CLI (--sem-llm, .env)
             └─ E5 execução real com chave
                 └─ E6 revisão humana → NARRATIVAS_APROVADAS
```

## Task List

### Fase 1: Núcleo sem rede
- [x] E1: Fatos do Epic do Escalar + anonimização
- [x] E2: Prompt + validador

### Checkpoint A
- [x] `pytest -q` passa; fatos dos Epics do Escalar reais montados sem nome de pessoa

### Fase 2: Chamada e integração
- [x] E3: Cliente OpenAI (requests) + orquestrador com cache e CSV
- [x] E4: Painel + CLI + bloco OpenAI no `.env`

### Checkpoint B
- [x] `radar relatorio` nos dados reais sem chave: painel igual ao de hoje (critério 1)
- [x] Cliente falso nos dados reais: Epics do Escalar narrados, CSV gravado, 2ª execução com zero chamadas e mesmo HTML

### Fase 3: Validação (depende do usuário)
- [x] E5: Execução real com chave — 28/28 válidas, 0 rejeitadas, 23 s
- [x] E6: Revisão humana das narrativas → `NARRATIVAS_APROVADAS = True` (2026-11-11)

## Risks and Mitigations

| Risco | Impacto | Mitigação |
|---|---|---|
| LLM inventa número ou causa | Alto | Validador determinístico; rótulo "causa provável"; fatos sempre visíveis; revisão humana |
| Nome de pessoa vaza no payload | Alto | Substituição em todos os campos + teste que serializa o payload e procura os nomes |
| Chave aparece em log/erro | Alto | Mensagens de erro só com status HTTP/tipo da exceção; teste dedicado |
| Validador rejeita demais (LLM reescreve "2,1×" como "duas vezes") | Médio | Prompt manda copiar números como estão; palavras sem dígitos passam; medir taxa em E5 |
| Formato de número diferente ("45%" vs "0,45") | Médio | Fatos vão formatados como no painel (vírgula decimal, %); validador compara texto |
| Modelo indisponível / 429 | Baixo | `status=erro`, painel sai; rodar de novo reaproveita o que deu certo |

## Open Questions
- Valor de `OPENAI_MODEL` (o usuário define no `.env`).
