# Implementation Plan: Agente de Riscos v1

> Spec: [SPEC-agente-de-riscos.md](../../SPEC-agente-de-riscos.md) (aprovada em 2026-11-05; calibragem do planejamento registrada nela)
> Tarefas: [todo.md](todo.md) · Plano do Radar (separado, ainda aberto): [../plan.md](../plan.md)
> Status: **aprovado e concluído em 2026-11-05** (R1–R7; aba Riscos liberada)

## Overview

Um pacote `riscos/` que reaproveita `radar.dados` e `radar.previsao` para deduzir, por regra,
os riscos de cada Epic aberto (6 categorias), classificá-los (probabilidade × impacto →
criticidade), marcar os que precisam ser escalados e comparar com a semana anterior. O mesmo
`radar relatorio` grava `riscos-AAAA-MM-DD.csv` e o painel HTML ganha a aba **Riscos**.

## O que a investigação de planejamento mostrou

Um protótipo descartável (fora do projeto) rodou as regras da spec nos dados reais (`out/Atlas/20261105T003131Z`, hoje = 05/11/2026):

| Medida | Resultado |
|---|---|
| Riscos (regra original de escopo) | 401 em 240 dos 242 Epics abertos |
| Por categoria | PRAZO 172 (29 materializados) · ESCOPO 109 · CAPACIDADE 61 · GOVERNANCA 31 · DEPENDENCIA 20 · QUALIDADE 8 |
| Crescimento de escopo | contra o escopo atual, 75 Epics disparam, a maioria Epics novos; contra o escopo de 4 semanas atrás (mín. 5 itens), 34 → **regra ajustada na spec** |
| Restante por Epic | mediana 7 · p75 22 · p90 49 → cortes de impacto 30/10 **mantidos** |
| Escalar | 35 riscos em **26 Epics** (data próxima 21 · dependência entre programas 7 · sem dono 5 · atraso grande 4) → **agrupado por Epic** no painel |
| Epics com dependentes | 34 com ≥ 1, 16 com ≥ 2 |
| Tempo do protótipo | cerca de 2 s (inclui ler o `workitem_links.csv` de 29 MB) |

Consequência para o produto: quase todo Epic tem algum risco. O valor para a diretoria está na
**categoria, na criticidade e no Escalar**, não na contagem. O painel abre no Escalar.

## Architecture Decisions

- **Regras puras, uma função por categoria.** `risco_<categoria>(contexto) -> (probabilidade, evidências) | None`.
  Cada uma é testável isoladamente nos dois lados de cada limiar.
- **Razão de ritmo sem Monte Carlo.** Extrair de `radar.previsao.prever` uma função pura
  `razao_ritmo(restante, ritmo_medio, entrada_media, dias_ate_alvo)`, que o `prever` passa a usar.
  O Radar não muda de comportamento: o CSV do Radar tem de sair **idêntico** antes e depois (teste de regressão).
  A spec do Radar está congelada (v3), e isso é refatoração, não mudança de modelo.
- **`dados.py` ganha o que falta, sem quebrar o que existe.** `Dados` recebe campos novos
  (`epic_de`, `faults`, `dependencias`); os campos atuais ficam iguais. Os links são lidos em
  streaming, guardando só `Successor` entre work items.
- **Dependência resolvida em duas passadas.** Primeiro as categorias que não dependem de outros
  Epics (PRAZO etc.); depois DEPENDENCIA, que consulta o PRAZO do Epic do predecessor. Sem ciclo.
- **Registro = lista de `Risco` ordenada por id.** O CSV é a fonte do movimento semanal: o
  `registro` lê o `riscos-*.csv` anterior mais recente com data < hoje. Nenhum outro estado.
- **Painel reaproveita o CSS e o JS de filtros do Radar.** `riscos/painel.py` gera só o miolo da
  aba; `radar/relatorio.py` monta as abas. As abas funcionam sem JS (as duas aparecem, uma embaixo da outra).
- **Versão das regras.** `REGRAS_VERSAO = "r1"` gravada em cada linha do CSV, como o `MODELO_VERSAO` do Radar.

## Dependency Graph

```
R1 dados + razao_ritmo (regressão do Radar)
 └─ R2 regras (6 categorias)
     └─ R3 classificação (impacto, matriz, gatilhos)
         └─ R4 registro + CSV + movimento + CLI      ← primeira fatia de ponta a ponta
             └─ R5 aba Riscos: abas, cartões, tabela, filtros
                 └─ R6 aba Riscos: Escalar por Epic, matriz, categorias, "saíram"
                     └─ R7 portão: revisão do painel pelo usuário (MVP estático)
```

Tudo é sequencial: cada tarefa usa os tipos da anterior. R5 e R6 poderiam ser uma só, mas
juntas passariam de 5 arquivos e de uma sessão.

## Task List

### Fase 1: Fundação
- [x] R1: Dados de risco (Epic de cada item, Faults, dependências) e `razao_ritmo` pura
- [x] R2: Regras das 6 categorias

### Checkpoint A
- [x] `pytest -q` passa; CSV do Radar idêntico ao de antes
- [x] Contagens por categoria nos dados reais batem com o protótipo (com a regra de crescimento ajustada)

### Fase 2: Registro
- [x] R3: Impacto, criticidade e gatilhos de Escalar
- [x] R4: Registro, CSV semanal, movimento e integração no `radar relatorio`

### Checkpoint B
- [x] `riscos-2026-11-05.csv` nos dados reais; Escalar ≈ 26 Epics; duas execuções = CSVs idênticos; < 60 s
- [x] Movimento conferido simulando uma semana anterior

### Fase 3: Painel
- [x] R5: Abas Radar | Riscos, cartões, tabela e filtros
- [x] R6: Escalar agrupado por Epic, matriz P × I, gráfico por categoria, "Saíram do registro"

### Checkpoint C
- [x] Critérios de sucesso 1–8 da spec
- [x] 3 riscos conferidos com o ADO (PRAZO, DEPENDENCIA, QUALIDADE), só leitura
- [x] Revisão humana do painel; começa a janela de 2 semanas

### Fase 4: Portão
- [x] R7: Revisão do painel pelo usuário; aprovado → aba Riscos sem o aviso

## Risks and Mitigations

| Risco | Impacto | Mitigação |
|---|---|---|
| Refatorar `prever` muda o Radar congelado (v3) | **Alto** | Teste de regressão: CSV do Radar byte a byte igual antes e depois de R1 |
| Quase todo Epic tem risco → registro vira ruído | Alto | Painel abre no Escalar agrupado por Epic; filtros por criticidade e categoria |
| Direção do link `Successor` invertida | Alto | Teste com link sintético; conferir 1 dependência real no ADO (Checkpoint C) |
| `workitem_links.csv` grande (29 MB) deixa o relatório lento | Médio | Leitura em streaming, só `Successor`; medir no Checkpoint B (meta < 60 s) |
| Movimento falso por id instável | Médio | id = Epic × categoria; teste com dois CSVs consecutivos |
| ~~Rotina semanal não automatizada~~ | — | Resolvido (2026-11-05): o MVP é estático, sem agendamento; o portão virou a revisão de um painel |
| Evidências longas poluem a tabela | Baixo | Uma frase por regra; etiquetas como nos motivos do Radar |

## Open Questions

- Nenhuma bloqueante. As da spec (riscos que saem por fechamento, Issues e Blockers do ADO, LLM) ficam para depois da v1.

## Definition of Done (toda tarefa)

- Critérios de aceite atendidos e verificados rodando, não só escritos
- Testes novos falham sem a mudança e passam com ela; `pytest -q` inteiro passa
- Casos-limite: escopo vazio, restante 0, ritmo zero, sem data alvo, sem dono, Epic sem dependências
- Nenhuma chamada de rede; nada escrito no ADO
- Sem código morto ou print de debug; mudança restrita à tarefa
