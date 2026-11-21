# Implementation Plan: Dashboard Inteligente v1

> Spec: [SPEC-dashboard-inteligente.md](../../SPEC-dashboard-inteligente.md) · Tarefas: [todo.md](todo.md)
> Status: **aprovado em 2026-11-11** (usuário: "Salva e vai até o fim")

## Overview

O agente trabalha na geração do painel: `radar relatorio` produz, além da causa provável, a
pauta, as perguntas sugeridas e os resumos por recorte (LLM), e os textos por regra do
significado de cada filtro. Tudo vai num JSON embutido, que o JS mostra conforme a interação.
`radar perguntar` cobre o imprevisto, sem servidor.

## Architecture Decisions

- **Núcleo de LLM genérico (`explicacao/llm.py`).** A causa provável, a pauta, os resumos e as
  perguntas passam pelo mesmo caminho: anonimização, cache, cliente e validador. A chave da causa
  provável fica idêntica, para não regerar as narrativas já aprovadas.
- **Fatos sempre das linhas** do Radar e do registro, como na Explicação. Assim o validador
  compara com o que o painel mostra.
- **Explicar ao clicar = filtro + caixa.** Não cria um segundo tipo de clique nos cartões: o clique
  filtra e a caixa "Leitura do agente" explica. Só o Epic ganha painel lateral, porque tem
  conteúdo demais para a caixa.
- **JSON embutido** (`<script type="application/json">`, com `<` escapado): o HTML continua um
  arquivo único e estático.
- **`perguntar` regera o painel** chamando o mesmo fluxo de `relatorio`. Sem cache para perguntas,
  já que cada uma é única. A pauta e os resumos vêm do cache.

## Dependency Graph

```
D1 escopo alinhado ─┐
D2 núcleo LLM ──────┼─ D3 recortes/pauta/sugeridas ─┐
                    └─ D4 leitura por regra ────────┼─ D5 HTML ─ D6 CLI relatorio ─ D7 perguntar ─ D8 revisão
```

## Risks and Mitigations

| Risco | Impacto | Mitigação |
|---|---|---|
| Refatorar o núcleo muda a chave da causa provável e invalida as narrativas aprovadas | Alto | Teste de chave idêntica; checkpoint A confere 26 narrativas do cache |
| JSON embutido quebra o HTML (`</script>` em título) | Alto | `json.dumps` + troca de `<` por `<`; teste com título malicioso |
| Pergunta livre sem recorte reconhecido dá resposta vaga | Médio | Fatos gerais + instrução de dizer "os dados não respondem"; revisão com 10 perguntas reais |
| Resumos de programas pequenos (1–2 riscos) dizem pouco | Baixo | Aceito; o resumo é curto |
| HTML cresce | Baixo | ~18 resumos e ~250 Epics no JSON: dezenas de KB sobre os 700 KB atuais |
