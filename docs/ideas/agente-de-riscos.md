# Agente de Riscos — registro sintético de riscos (v1)

> Origem: sessão `idea-refine` de 2026-11-05. Dados de referência: extração `out/Atlas/20261105T003131Z`.

## Problem Statement
Como podemos dar à diretoria um registro de riscos do Atlas, classificado e com dono,
sem que ninguém precise mantê-lo, já que hoje não existe registro de riscos em uso no ADO?

## Recommended Direction
O agente deduz os riscos dos sinais de entrega que já estão no ADO e mantém o próprio
registro, sem nunca escrever no ADO. A unidade é **Epic × categoria** (ex.: `R-90006-PRAZO`),
com id estável entre semanas, o que dá de graça "novo / piorou / melhorou / sumiu" e a tendência.

Categorias v1, todas por regra:
- **Prazo:** Epic vermelho ou já atrasado no Radar
- **Dependência:** predecessor de outro Epic vencido ou em risco
- **Capacidade:** itens restantes sem responsável
- **Escopo:** sem escopo detalhado, ou escopo crescendo
- **Qualidade:** Faults e Bugs abertos sob o Epic
- **Governança:** sem data alvo

A probabilidade é classificada **por regra, em faixas** (alta, média, baixa), e não pela chance
do Monte Carlo, que só será validada em 28/12. O impacto vem do escopo restante, da proximidade
da data e do nº de Epics dependentes. O dono é o responsável pelo Epic.

Entrega junto com o Radar: uma aba "Riscos" no mesmo painel HTML semanal, com o registro completo
e filtros. Riscos que disparam um gatilho de escalonamento ganham a marca **Escalar** e ficam no
topo. Gatilhos: data alvo próxima, dependência entre programas, atraso grande ou sem dono.

### O que os dados mostraram (05/11/2026)
- 71 work items `Risk` existem, mas o registro não está em uso (confirmado pelo usuário):
  69 sem pai, cerca de 6 com Action de mitigação, campos de impacto e probabilidade quase vazios.
- 379 dependências Predecessor→Successor com os dois lados abertos; 130 entre programas;
  42 com o predecessor vencido.
- Pelos links entre Epics, só 16 Epics dependem de outro Epic vencido ou em risco, e 12 deles
  o Radar já marca. A dependência vale mais como explicação e gatilho do que como descoberta.
- Gatilhos sobre os dados de hoje: 39 Epics vermelhos com alvo em até 4 semanas; 4 já atrasados
  há mais de 8 semanas; 19 Epics vermelhos sem responsável.
- 315 Faults e 111 Bugs abertos (sinal de qualidade).

## Key Assumptions to Validate
- [ ] Faixas de probabilidade por regra ordenam os riscos de forma crível — a diretoria revisa os
      Escalar nas 2 primeiras semanas
- [ ] Os gatilhos cortam para um número legível de Escalar por semana (hoje seriam cerca de 50,
      a calibrar) — contar nos dados reais antes de fixar
- [ ] O id Epic × categoria é estável entre extrações — teste com dois CSVs consecutivos
- [ ] Faults e Bugs ligados a Epics indicam risco de qualidade real — conferir 3 casos com o ADO
- [ ] Responsável do Epic é um dono aceitável — 19 Epics vermelhos estão sem responsável

## MVP Scope
Dentro:
- `riscos/`, reaproveitando `radar.dados` e a previsão do Radar
- 6 categorias por regra, probabilidade × impacto em faixas
- `relatorios/riscos-AAAA-MM-DD.csv` (o registro, com histórico)
- aba "Riscos" no painel com filtros e a marca Escalar
- comparação com a semana anterior: novo, piorou, melhorou, sumiu
- testes com dados sintéticos

Fora: tudo da lista abaixo.

## Not Doing (and Why)
- Escrever no ADO (criar Risks, Actions) — ADO é somente leitura; o registro vive no agente
- Usar a chance numérica do Radar — modelo não validado até 28/12
- LLM lendo descrições e comentários — sem registro base não dá para medir se acerta;
  exige anonimização; entra atrás de interface depois
- Score de saúde por programa — nota agregada esconde o porquê
- Riscos fora de Epic (Faults e Requests soltos) — sem dono nem data para escalar
- Usar os 71 Risks existentes como fonte — registro não está em uso
- Alertas fora do relatório semanal (Teams, e-mail) — mesmo canal do Radar por ora

## Open Questions
- Qual corte dos gatilhos deixa o Escalar legível? (ex.: alvo em até 2 semanas em vez de 4;
  atraso > 4 semanas)
- Impacto: há algum campo de valor de negócio confiável (`area_valor`?) ou fica só no tamanho
  e nas dependências?
- O que fazer com risco que "sumiu": mitigado ou materializado? (ex.: Epic fechado vs.
  data passou)
- A aba Riscos herda o aviso "uso interno" até a T8, ou regras puras podem ir direto para
  a diretoria?
