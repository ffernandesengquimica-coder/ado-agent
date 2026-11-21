# ADO Agent

Camada de inteligência sobre um projeto do Azure DevOps (ADO). Extrai os dados do projeto em modo somente leitura, prevê quais Epics vão estourar a data alvo, monta um registro de riscos e gera um painel HTML para a reunião de acompanhamento, com textos explicativos escritos por LLM.

Tudo roda localmente e sob demanda. Não há banco de dados, serviço agendado nem escrita no ADO.

## O que faz

| Módulo | Função |
|---|---|
| `extrator/` | Lê work items, links, hierarquia e wiki pela API REST do ADO (só `GET`) e grava em CSV. |
| `radar/` | Radar de Datas: previsão por Epic com simulação de Monte Carlo, backtest, relatório e servidor local do painel. |
| `riscos/` | Registro de riscos por regras determinísticas, com criticidade e lista de escalonamento. |
| `explicacao/` | Textos do painel escritos por LLM (causa provável, pauta, resumos, respostas), com anonimização e validação. |

### Radar de Datas

Para cada Epic aberto, mede quantos itens foram entregues e quantos entraram por semana nas últimas 12 semanas e simula 10.000 futuros possíveis. O resultado é a chance de cumprir a data alvo:

- **vermelho**: abaixo de 40%
- **amarelo**: de 40% a 70%
- **verde**: 70% ou mais
- **já atrasado**: data alvo vencida
- **sem como prever**: Epic sem data alvo ou sem histórico de entrega

O `backtest` roda o mesmo código em datas de corte passadas e compara com o que aconteceu. O modelo só passa no portão com recall ≥ 70%, precisão pelo menos 10 p.p. acima da taxa base e F1 acima dos preditores ingênuo e trivial.

### Registro de riscos

Seis categorias, todas calculadas por regra, sem LLM: `PRAZO`, `DEPENDENCIA`, `CAPACIDADE`, `ESCOPO`, `QUALIDADE` e `GOVERNANCA`. Cada risco traz a evidência em uma frase com números.

A criticidade vem da matriz probabilidade × impacto. O impacto mede o tamanho do trabalho restante e quantos Epics dependem daquele. Um risco entra na lista **Escalar** quando dispara um destes gatilhos:

- Epic crítico com data alvo nos próximos 28 dias
- dependência de alta probabilidade entre programas diferentes
- atraso maior que 8 semanas
- Epic crítico sem responsável

Cada relatório é comparado com o anterior, para mostrar o que entrou, saiu ou mudou.

### Textos do agente

O LLM recebe apenas fatos já calculados (números, datas, ids, evidências) e escreve:

- a causa provável de cada Epic da lista Escalar
- a pauta da reunião
- um resumo por filtro (programa ou categoria de risco)
- respostas a perguntas sugeridas e a perguntas livres

Todo texto passa por um validador determinístico antes de aparecer no painel: se citar número, data, id ou pessoa que não estava nos fatos enviados, é rejeitado. Os textos aceitos ficam em cache, e `--sem-llm` regenera o painel sem nenhuma chamada nova.

## Instalação

Requer Python 3.12 ou mais recente.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuração

Copie `.env.example` para `.env` e preencha:

| Variável | Para quê |
|---|---|
| `ADO_ORG` | Organização, o `{org}` de `https://dev.azure.com/{org}` |
| `ADO_PROJECT` | Nome do projeto como aparece no ADO |
| `ADO_PAT` | Personal Access Token com escopos **somente leitura** (Work Items, Project and Team, Analytics, Wiki) |
| `OPENAI_API_KEY` | Chave da OpenAI. Sem ela, o painel usa só os textos em cache |
| `OPENAI_MODEL` | Modelo a usar. Vazio, o painel sai sem textos de LLM |

As demais variáveis têm padrão e estão comentadas no `.env.example`.

## Uso

```powershell
python -m extrator                      # extrai tudo para out/<projeto>/<carimbo>/
python -m radar backtest                # mede o acerto do modelo em cortes passados
python -m radar relatorio               # gera os CSVs e o painel HTML do dia em relatorios/
python -m radar relatorio --sem-llm     # idem, sem chamar a OpenAI
python -m radar perguntar "por que Obras Sul piorou?"
python -m radar servir                  # painel em http://127.0.0.1:8765/ com caixa de pergunta
```

Os comandos do `radar` aceitam `--extracao <pasta>` (padrão: a extração mais recente), `--saida <pasta>` (padrão: `relatorios`), `--hoje AAAA-MM-DD` e `--semente <n>`.

O servidor local só escuta em `127.0.0.1` e só aceita perguntas vindas da própria página.

### Arquivos gerados

| Pasta | Conteúdo |
|---|---|
| `out/<projeto>/<carimbo>/` | CSVs da extração e `_manifesto.csv` com a contagem de linhas |
| `relatorios/` | `radar-<data>.csv`, `riscos-<data>.csv`, `radar-<data>.html`, cache de textos e resultado do backtest |
| `logs/` | Um log por extração |

## Demonstração com dados sintéticos

Para ver o painel sem acesso a um ADO, abra `demo/painel/radar-2026-11-17.html` no navegador. Ele foi gerado a partir de uma extração inventada: o projeto "Atlas", com 34 Epics em 5 programas, em que cada Epic segue um perfil escolhido para exercitar uma parte do painel (farol, atraso, escopo vazio, falta de dono, qualidade, dependência entre programas).

Para gerar de novo:

```powershell
python demo/gerar_extracao.py
python -m radar relatorio --extracao demo/dados/sintetica --saida demo/painel --hoje 2026-11-10 --sem-llm
python -m radar relatorio --extracao demo/dados/sintetica --saida demo/painel --hoje 2026-11-17
```

A primeira execução do relatório serve de "semana anterior" para a comparação de riscos. A segunda chama a OpenAI se houver chave no `.env`; os textos já gerados estão em `demo/painel/` e são reaproveitados do cache. Para a caixa de pergunta, use `python -m radar servir --saida demo/painel --hoje 2026-11-17`.

## Privacidade e dados

Este repositório contém **somente código e testes**. Nenhum dado do ADO é versionado.

- `out/`, `relatorios/`, `logs/` e `.env` estão no `.gitignore`. Esses arquivos contêm nomes de pessoas, e-mails, títulos de work items e credenciais, e ficam apenas na máquina de quem roda.
- Os testes usam extrações sintéticas criadas em `tests/conftest.py`.
- Nomes de projeto, programas, pessoas e ids de work items que aparecem no código, nos testes e na documentação (`SPEC-*.md`, `docs/`, `tasks/`) são **fictícios** (por exemplo, o projeto "Atlas" e os programas "Rede Norte" e "Obras Sul"). Os números da documentação vêm de um projeto real, sem identificação da empresa.
- O acesso ao ADO é somente leitura: o cliente HTTP só faz `GET` e o PAT deve ter apenas escopos de leitura.

O que vai para a OpenAI:

- Vão apenas fatos já calculados sobre cada Epic. Descrições, comentários e páginas de wiki não são enviados.
- Nomes de pessoas são trocados por `Pessoa A`, `Pessoa B`… antes do envio, e o mapa de volta nunca sai da máquina.
- **Não são anonimizados:** títulos de Epics, nomes de programas e ids de work items. Avalie isso antes de usar em um projeto com títulos sensíveis.

O painel HTML e os CSVs de `relatorios/` mostram os nomes reais, porque são feitos para uso interno. Não os publique.

## Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

Nenhum teste acessa o ADO nem a OpenAI.

## Limitações

- A janela de ritmo e as datas de corte padrão do backtest (`radar/previsao.py`, `radar/__main__.py`) foram calibradas para um projeto específico. Ajuste-as antes de usar em outro.
- A execução é manual. Não há agendamento nem histórico além dos arquivos em `relatorios/`.
