# Implementation Plan: Radar de Datas — Agente de Insights v1

> Spec: [SPEC-radar-de-datas.md](../SPEC-radar-de-datas.md) (aprovada em 2026-11-04)
> Tarefas: [todo.md](todo.md)
> Status: **aprovado em 2026-11-04** · v3 congelada; relatório interno pronto (T1–T7); T8 em 2026-12-28

## Overview

Um pacote `radar/` que lê os CSVs do `extrator`, prevê por Monte Carlo a chance de
cada Epic aberto cumprir a data alvo e gera um relatório HTML semanal para a diretoria.
O backtest é construído **antes** do relatório: ele é o portão que decide se o
relatório vai para a diretoria.

## O que a investigação de planejamento mostrou

Contagens nos dados reais (`out/Atlas/20261105T003131Z`), pela definição da spec:

| Corte T | Epics avaliáveis | Atrasaram | Features avaliáveis | Atrasaram |
|---|---|---|---|---|
| 2026-07-06 | 67 | 41 (61%) | 247 | 174 (70%) |
| 2026-08-03 | 71 | 46 (65%) | 272 | 209 (77%) |
| 2026-08-31 | 69 | 43 (62%) | 243 | 188 (77%) |

- **Amostra suficiente** (Open Question 1 da spec): cerca de 70 Epics por corte. Os cortes compartilham Epics, então as métricas agregadas não são independentes; o backtest reporta também o nº de Epics únicos.
- **Fechamento administrativo** (Open Question 2): só 3 dos 111 Epics Done têm menos de 90% do escopo concluído. É desprezível, e a regra da spec fica como está.
- ⚠️ **Taxa base alta (cerca de 63%)**: o preditor trivial "todos atrasam" tem recall de 100% e precisão de cerca de 63%, e passava no portão original da spec. Ver "Decisão sobre o portão".
- Há 242 Epics abertos: 211 com data alvo e 200 com escopo.

## Architecture Decisions

- **Backtest antes do relatório.** A premissa mais arriscada é "o modelo prevê". Se ela falhar, não vale construir HTML. As tarefas 3 e 4 provam o modelo com os dados reais antes das tarefas 5 a 7.
- **Uma função de previsão para o presente e para o passado.** `prever(epic, itens, hoje, rng)` não sabe se `hoje` é real ou um corte T. O backtest só reconstrói os itens "como eram em T" e chama a mesma função. Assim, o backtest testa exatamente o código que gera o relatório.
- **Monte Carlo vetorizado em numpy.** Cada Epic usa uma matriz execuções × semanas sorteadas, sem laço Python por execução. São 242 Epics × 10 mil execuções, bem dentro de 60 s.
- **Datas tipadas na fronteira.** `dados.py` converte strings em `date` uma vez; o resto do código nunca vê strings de data.
- **Dois baselines no backtest:** o ingênuo da spec (% concluído < % tempo decorrido) e o trivial "todos atrasam". Ambos sempre aparecem na tabela de métricas, independentemente da decisão sobre o portão.
- **Ambiente isolado.** `.venv` com Python 3.12. O `python` padrão é o venv do hermes-agent, que não tem pandas nem pytest.

## Dependency Graph

```
T1 ambiente + esqueleto CLI
 └─ T2 dados (Epics, escopo, datas)
     └─ T3 previsao (ritmo, Monte Carlo, farol)
         ├─ T4 backtest + CLI `radar backtest`      ← portão
         │    └─ [checkpoint: decisão do portão com o humano]
         ├─ T5 motivos
         └─ T6 CLI `radar relatorio` → CSV          (depende de T3, T5)
              └─ T7 HTML + interface Narrador
```

T5 pode ser feita em paralelo com T4, mas só vale a pena depois que o portão passar.

## Task List

### Fase 1: Fundação
- [ ] T1: Ambiente, dependências e esqueleto do CLI
- [ ] T2: Carga dos dados: Epics e escopo com datas tipadas

### Checkpoint A: Fundação
- [ ] `pytest -q` passa; `python -m radar --help` lista `relatorio` e `backtest`
- [ ] Contagens de `dados` nos CSVs reais batem com a investigação (242 Epics abertos, 200 com escopo)

### Fase 2: Provar o modelo
- [ ] T3: Previsão: ritmo semanal, Monte Carlo e farol
- [ ] T4: Backtest e comando `radar backtest`

### Checkpoint B: Portão (revisão humana obrigatória)
- [ ] `radar backtest` roda nos dados reais e gera `relatorios/backtest-*.csv`
- [ ] Modelo comparado com os dois baselines; resultado mostrado ao humano
- [ ] Se necessário, o ajuste único dos cortes do farol é registrado na spec
- [ ] **Passou** → Fase 3. **Não passou** → voltar à spec (não construir o relatório)

### Fase 3: Relatório
- [ ] T5: Motivos por regra
- [ ] T6: Comando `radar relatorio` gerando o CSV por Epic
- [ ] T7: Relatório HTML e interface `Narrador`

### Checkpoint C: Completo
- [ ] Critérios de sucesso 1–9 da spec atendidos
- [ ] 3 Epics conferidos manualmente com o ADO (leitura)
- [ ] Revisão humana do HTML antes de enviar para a diretoria

## Risks and Mitigations

| Risco | Impacto | Mitigação |
|---|---|---|
| Portão fraco: "todos atrasam" passa com taxa base de 63% | **Alto** | Portão revisado na spec: precisão ≥ taxa base + 10 p.p. e F1 > os dois baselines |
| Vazamento de futuro na reconstrução em T | Alto | Teste dedicado em T4: itens criados ou fechados depois de T não influenciam |
| Data alvo atual usada no passado (sem histórico de datas) | Médio | Limitação aceita na spec; reportada junto com as métricas |
| Cortes correlacionados (mesmo Epic em 3 cortes) | Médio | Reportar nº de Epics únicos e métricas por corte, não só o agregado |
| Relatório quase todo vermelho, dado o atraso generalizado | Médio | Ordenar por probabilidade e por data; o valor para o executivo está na priorização e nos motivos |
| Ambiente Python errado (hermes venv) | Baixo | T1 cria o `.venv`; a spec manda sempre usar `.venv\Scripts\python` |

## Decisão sobre o portão (resolvida)

O portão original não excluía o preditor trivial. Aprovado: recall ≥ 70%, precisão ≥
taxa base + 10 p.p., e F1 maior que os dois baselines. A spec foi atualizada.

## Open Questions

- Escopo que cresce (Open Question 3 da spec): sem mudança, o CSV semanal começa a guardar o histórico.
- Etapa 2 (LLM): fora deste plano.

## Definition of Done (toda tarefa)

- Critérios de aceite da tarefa atendidos e verificados rodando, não só escritos
- Testes novos falham sem a mudança e passam com ela; `pytest -q` inteiro passa
- Casos-limite tratados (escopo vazio, ritmo zero, data vencida, data ausente)
- Sem código morto ou print de debug; mudança restrita à tarefa
- Nenhuma chamada de rede no `radar`
