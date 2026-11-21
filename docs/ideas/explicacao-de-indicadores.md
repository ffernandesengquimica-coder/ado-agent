# Explicação de Indicadores v1 — causa provável por Epic (LLM)

> Sessão: RUN_LOG-Felipe-2026-11-11-19-23.md · Proposta: Proposta.jpg (5. Saídas & Produtos → Explicação de Indicadores)

## Problem Statement

Como a diretoria pode entender, sem abrir o ADO, *por que* um Epic do Escalar está em
risco — ligando os motivos do Radar, as evidências dos Riscos e as dependências numa
explicação só?

## Recommended Direction

Para cada Epic marcado "Escalar" (~28 em 11/11), um LLM da OpenAI redige 2–3 frases de
**causa provável**, dentro do painel atual (na linha do Epic). O LLM não calcula nada:
recebe só fatos já calculados pelo Radar e pelo Agente de Riscos (motivos, evidências por
categoria, dependências do `workitem_links.csv`, números) e os ordena numa relação de
causa e efeito. Abaixo da frase, a lista dos fatos que a sustentam.

Nomes de pessoas são anonimizados antes do envio ("Pessoa A") e re-identificados
localmente; títulos, áreas e números vão como estão. Temperatura 0 e cache em CSV por
hash da entrada: rodar de novo com a mesma entrada não chama a API. Sem chave ou sem
rede, o painel sai igual, só sem narrativa (`NarradorNulo`).

A narrativa só vai para a diretoria depois da sua revisão de um painel, como foi com a
aba Riscos. Até lá aparece marcada "em validação".

Por que o LLM aqui e não em outras partes: ele é bom em juntar vários fatos numa frase
com sentido e ruim em garantir número exato. Significado das métricas, selo de confiança
e detecção de mudanças ficam melhores por regra.

## Key Assumptions to Validate

- [ ] Os fatos calculados contêm a causa — revisão humana das 28 narrativas: alguma
      "soa certa e está errada"?
- [ ] O LLM não inventa números nem dependências — validador automático: todo número da
      saída existe na entrada; dependência citada existe nos links; falhou → descartada
- [ ] A diretoria prefere a narrativa aos chips — comparação lado a lado de 10 Epics
- [ ] Custo e tempo aceitáveis — medir tokens e segundos por execução (meta: < 1 min extra)

## MVP Scope

- **Dentro:** `OPENAI_API_KEY` e `OPENAI_MODEL` no `.env` (com `.env.example`);
  `NarradorOpenAI` implementando a interface `Narrador` atual; montagem dos fatos por
  Epic (Radar + Riscos + dependências); anonimização de pessoas; validador de números;
  cache em `relatorios/narrativas-AAAA-MM-DD.csv`; exibição na linha do Epic com rótulo
  "causa provável" + fatos; aviso "em validação" até `NARRATIVAS_APROVADAS`.
- **Fora:** tudo o que está abaixo.

## Not Doing (and Why)

- "O que mudou e por quê" — exige o módulo de diff entre CSVs; próxima versão
- Resumo executivo no topo — encosta no Executive Brief; fica para lá
- Selo de confiança e "o que o número significa" — melhores por regra, não por LLM; outra entrega
- "O que faria virar verde" — é recomendação (outro agente) e exige rodar o Monte Carlo de novo
- Epics fora do Escalar — expandir para "vermelhos com ≥ 3 fatos" é trocar um filtro, depois da validação
- Azure OpenAI / anonimização total — decisão: OpenAI direta, só pessoas anonimizadas
- LLM decidindo cor, chance ou criticidade — a conta é sempre do Python

## Open Questions

- Qual modelo da OpenAI (fica configurável em `OPENAI_MODEL`; escolher na spec pelo custo)
- Dependências entram como fato só quando o predecessor está vencido ou em risco, ou sempre?
- A narrativa também aparece na aba Riscos ou só na linha do Epic no Radar?
