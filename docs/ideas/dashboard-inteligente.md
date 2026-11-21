# Dashboard Inteligente v1 — o agente dentro do painel

> Sessão: RUN_LOG-Felipe-2026-11-11-20-07.md · Base: Radar de Datas + Agente de Riscos + Explicação de Indicadores (v1 liberada em 11/11)

## Problem Statement

Como fazer o painel semanal deixar de ser um relatório que se lê e virar um dashboard que
conduz a reunião da diretoria — destacando o que decidir, explicando o que se clica,
resumindo o recorte filtrado e respondendo perguntas — sem servidor, sem chave no HTML
e sem chat ao vivo arriscado?

## Recommended Direction

O agente trabalha **antes** da reunião: `radar relatorio` gera, junto com o painel, os
textos que o HTML exibe conforme a interação. A pauta da semana (3–5 pontos de decisão
escolhidos por regra, redigidos pelo LLM) abre o painel e cada ponto leva ao detalhe;
"3 perguntas que vocês deveriam fazer hoje" vêm já respondidas. Um resumo por recorte
(geral, 11 programas, 6 categorias ≈ 18 textos) troca no topo quando você filtra. Clicar
num número, cartão ou célula abre um painel lateral com a explicação por regra; clicar num
Epic mostra a causa provável.

Para o que ninguém previu, o **modo apresentador**: `radar perguntar "..."` no terminal.
Uma regra acha o recorte citado (programa, `#id`), manda só esses fatos (anonimizados), o
validador confere a resposta e ela entra na seção "Perguntas desta reunião" do HTML —
você lê antes de recarregar a tela. As perguntas feitas ficam gravadas e viram a base de
perguntas antecipadas no futuro.

Tudo continua estático e manual. Mesmas garantias da v1 da Explicação: LLM só redige
fatos calculados, nomes anonimizados, validador de números, cache por hash. Todo texto que
citar números do Radar leva o selo "previsão em validação" até o teste de 28/12.

## Key Assumptions to Validate

- [ ] Você filtra durante a apresentação — observar na 1ª reunião se o resumo por recorte aparece
- [ ] A regra de recorte acerta os fatos de perguntas livres — testar com 10 perguntas reais suas antes da reunião
- [ ] Pauta escolhida por regra bate com o que você destacaria — revisar a pauta de 11/11 lado a lado com a sua
- [ ] Resumos sem contradição entre abas — alinhar a regra de crescimento de escopo antes (pré-requisito)

## MVP Scope

- **Pré-requisito:** motivo de crescimento de escopo do Radar alinhado ao dos Riscos (contra
  o escopo de 4 semanas atrás, mín. 5 itens); modelo v3 intacto; narrativas afetadas regeradas
- **Dentro:** pauta; perguntas sugeridas; resumo por recorte com troca por filtro; painel
  lateral (regra para números/células, causa provável para Epics do Escalar); `radar perguntar`
  com seção "Perguntas desta reunião"; selo "previsão em validação" quando citar o Radar
- **Fora:** tudo abaixo

## Not Doing (and Why)

- Chat ao vivo no HTML / servidor local — exige chave fora do HTML e expõe erro do LLM ao vivo; v2, se houver demanda
- Banco de perguntas antecipadas com busca — sem perguntas reais é palpite; nasce das perguntas do modo apresentador
- Causa provável para ~160 Epics — mais texto e custo sem pedido; expandir é trocar um filtro
- Recomendações ("o que fazer") — é o Agente de Recomendações, outra entrega
- Power BI, Teams, e-mail — você apresenta pelo HTML; outros canais depois
- Agendamento — MVP estático

## Open Questions

- A pauta fica fixa no topo ou numa aba própria "Reunião"?
- Perguntas desta reunião: ficam só no HTML do dia ou acumulam num histórico?
