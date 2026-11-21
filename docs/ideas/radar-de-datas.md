# Radar de Datas — Agente de Insights (v1)

## Problem Statement
Como poderíamos avisar a diretoria, semanas antes, quais Epics do projeto Atlas
não vão cumprir a data alvo, com evidência suficiente para agir?

## Recommended Direction
Um relatório semanal, por Epic, que compara o ritmo real de entrega com o ritmo
necessário para cumprir a data alvo. Por baixo: simulação Monte Carlo sobre o
histórico semanal de fechamento dos descendentes do próprio Epic (últimas 8–12
semanas), gerando a probabilidade de cumprir a data. Para o executivo: farol
(verde/amarelo/vermelho), a probabilidade e uma frase de porquê.

A conta é determinística (Python sobre os CSVs extraídos). O LLM só entra no
fim, recebendo os números já calculados e os dados anonimizados, para explicar
cada Epic vermelho (escopo cresceu, nada andou há N semanas, filhos sem
responsável) e redigir o texto. O LLM nunca calcula a previsão.

Usar o ritmo do próprio Epic evita o problema mais difícil, que é mapear times
e dividir capacidade entre trabalhos paralelos, e dá números grandes o
suficiente para uma estatística estável.

## Key Assumptions to Validate
- [ ] O ritmo passado prevê o futuro → backtest: rodar o modelo "como se fosse"
      01/07, 01/08 e 01/09 e medir quantos Epics previstos como vermelhos de fato
      atrasaram (precisão/recall). Meta: acertar mais do que "repetir a semana passada".
- [ ] PBIs são fechados quando o trabalho termina → no backtest, olhar
      fechamentos em lote fora de fevereiro (picos > 3× a mediana semanal).
- [ ] Epics são detalhados cedo → medir, nos Epics já concluídos, quando os
      filhos foram criados em relação à data alvo.
- [ ] A diretoria age com base no farol → mostrar a primeira versão para 1–2
      executivos e perguntar qual Epic vermelho eles não conheciam.

## MVP Scope
Dentro:
- Epics abertos com data alvo; progresso medido por contagem de PBIs, Bugs,
  Habilitators e Spikes descendentes (story points estão 0% preenchidos)
- Ritmo a partir de 01/03/2026 (fevereiro = migração, fica de fora)
- Monte Carlo (10 mil execuções) → P(cumprir a data), data P50/P85
- Farol: razão entre o ritmo necessário e o ritmo real, com cortes ajustados no backtest
- Seções fixas: "vão atrasar" | "já atrasados" (data vencida) | "sem como prever"
  (sem filhos ou sem ritmo)
- Backtest antes do primeiro relatório
- Saída: um markdown/HTML gerado localmente; o LLM recebe só dados anonimizados

Fora: tudo da lista abaixo.

## Not Doing (and Why)
- Previsão por Feature ou por time — exige mapear capacidade compartilhada;
  as Features aparecem só como explicação dentro do Epic
- Initiatives — agregam demais para a v1; o roll-up vem depois se o Epic funcionar
- Story points / esforço — não existem nos dados
- Detectar risco em texto (variação 4) e escore aprendido (variação 7) —
  fora do modelo escolhido para o agente
- Alertas em tempo real, Teams, Power BI — o relatório semanal valida o valor primeiro
- Infraestrutura Azure (SQL, Cosmos, Search) — CSV + Python local até o backtest provar o modelo
- Histórico de revisões — o backtest usa criado_em/fechado_em; revisões
  (datas empurradas) ficam para a v2

## Open Questions
- Que nível de acerto no backtest torna o agente confiável o bastante para a diretoria?
- Escopo que cresce: o MVP projeta com o escopo atual (otimista). Basta isso
  ou precisamos de fotos semanais desde já?
- Itens Removed contam como "resolvidos" para o ritmo ou saem da conta?
- Qual provedor de LLM recebe o texto anonimizado na v1 (Azure OpenAI ou outro)?

## Contexto da decisão
- Usuário principal: diretoria/executivo; sucesso = antecipar problemas; entrega = relatório periódico
- Restrições: rodar local; dados anonimizados antes de qualquer LLM
- Datas alvo são compromissos reais (confirmado); fev/2026 = migração (confirmado)
- Sessão completa: RUN_LOG-Felipe-2026-11-04-21-40.md
