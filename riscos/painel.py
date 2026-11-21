"""Aba "Riscos" do painel semanal, gerada a partir das linhas do registro (o CSV).

Usa o mesmo CSS base e o mesmo script de filtros do Radar (`radar.relatorio`): cada
`data-filtro="x"` filtra as linhas `tr[data-x]` da tabela desta aba. Este módulo não
importa `radar.relatorio`; é o Radar que monta as abas.
"""
import unicodedata
from collections import Counter
from datetime import date
from html import escape

from .classificacao import CRITICIDADES
from .regras import CATEGORIAS

# Aprovado pelo usuário em 2026-11-05 (R7, revisão do painel); registrado na spec. False volta o aviso.
RISCOS_APROVADOS = True
# Causa provável (LLM): aprovada pelo usuário em 2026-11-11 (E6, revisão do painel). False volta o aviso "em validação".
NARRATIVAS_APROVADAS = True

CATEGORIA = {"PRAZO": "Prazo", "DEPENDENCIA": "Dependência", "CAPACIDADE": "Capacidade",
             "ESCOPO": "Escopo", "QUALIDADE": "Qualidade", "GOVERNANCA": "Governança"}
CRITICIDADE = {"critico": "Crítico", "alto": "Alto", "medio": "Médio", "baixo": "Baixo"}
PROBABILIDADE = {"alta": "Alta", "media": "Média"}
IMPACTO = {"alto": "Alto", "medio": "Médio", "baixo": "Baixo"}
GATILHO = {"data_proxima": "data alvo em até 4 semanas", "dependencia_entre_programas": "dependência entre programas",
           "atraso_grande": "atrasado há mais de 8 semanas", "sem_dono": "Epic sem dono"}
MOVIMENTO = {"novo": "novo", "piorou": "▲ piorou", "melhorou": "▼ melhorou", "igual": "igual"}

_COLUNAS = [
    ("Criticidade", "num", "Probabilidade × impacto: Crítico, Alto, Médio ou Baixo. A marca Escalar indica que o risco disparou um gatilho para a diretoria."),
    ("Epic", "num", "Id do Epic no Azure DevOps."),
    ("Título", "txt", "Título do Epic e a área (programa › time)."),
    ("Categoria", "txt", "Tipo do risco. 'Materializado' = o risco de prazo já aconteceu (data alvo vencida)."),
    ("Prob.", "num", "Probabilidade por regra (Alta ou Média). Não usa a chance do Monte Carlo do Radar."),
    ("Impacto", "num", "Pelo tamanho e pelas dependências: Alto = 30+ itens restantes ou 2+ Epics dependentes; Médio = 10+ itens, 1 dependente ou escopo ainda não detalhado."),
    ("Evidência", "txt", "Os números que fizeram a regra disparar."),
    ("Dono", "txt", "Responsável pelo Epic no ADO."),
    ("Data alvo", "txt", "Data alvo (Target Date) do Epic."),
    ("Movimento", "txt", "Comparação com o registro da semana anterior: novo, piorou, melhorou ou igual."),
]

_DEFINICOES = [
    ("Prazo", "O ritmo atual não fecha o restante até a data (precisa acelerar 1,0× ou mais), ou o Epic está parado há 4 semanas. Data alvo já vencida = materializado."),
    ("Dependência", "O Epic depende (link Successor) de um item de outro Epic que já venceu, cujo Epic já atrasou, ou cujo Epic tem risco de prazo alto."),
    ("Capacidade", "20% ou mais dos itens restantes estão sem responsável (50% ou mais = alta)."),
    ("Escopo", "Data marcada sem nenhum item detalhado, ou escopo que cresceu 20% ou mais nas últimas 4 semanas em relação ao que existia antes."),
    ("Qualidade", "Faults e Bugs abertos somam 20% ou mais do restante (50% ou mais = alta)."),
    ("Governança", "Epic aberto sem data alvo."),
    ("Escalar", "Risco Crítico com data alvo em até 4 semanas; dependência alta de outro programa; atraso de mais de 8 semanas; ou risco Crítico em Epic sem dono."),
]

CSS = """
.abas{gap:4px;margin:16px 0 4px;border-bottom:1px solid var(--linha)}
.abas button{background:none;border:0;border-bottom:3px solid transparent;padding:8px 14px;font-weight:600;cursor:pointer;color:var(--suave)}
.abas button[aria-selected=true]{color:var(--texto);border-bottom-color:var(--foco)}
.c-critico{--cor:#9b1c1c}.c-alto{--cor:#c2410c}.c-medio{--cor:#b7791f}.c-baixo{--cor:#6b6a66}
.c-escalar{--cor:#7c3aed}.c-materializado{--cor:var(--ja_atrasado)}
@media (prefers-color-scheme:dark){.c-critico{--cor:#f97066}.c-alto{--cor:#fb923c}.c-medio{--cor:#fdb022}
.c-baixo{--cor:#a9a8a3}.c-escalar{--cor:#c4b5fd}}
.escalar{margin-bottom:12px}.escalar table{min-width:760px}
.escalar td{vertical-align:top}.escalar .gat{color:var(--cor);font-size:12px;font-weight:600}
.ver{background:none;border:1px solid var(--linha);border-radius:6px;padding:2px 8px;cursor:pointer;font-size:12px;white-space:nowrap}
.ver[aria-pressed=true]{border-color:var(--foco);background:color-mix(in srgb,var(--foco) 14%,transparent)}
.matriz{display:grid;grid-template-columns:auto repeat(3,1fr);gap:6px;align-items:stretch}
.matriz .eixo{font-size:12px;color:var(--suave);display:flex;align-items:center;justify-content:center;text-align:center}
.celula{border:0;border-radius:8px;padding:12px 6px;cursor:pointer;color:#fff;background:var(--cor);text-align:center}
.celula b{display:block;font-size:22px;line-height:1.1}.celula span{font-size:12px;opacity:.9}
.celula[aria-pressed=true]{outline:3px solid var(--texto);outline-offset:1px}
.celula.zero{background:color-mix(in srgb,var(--cor) 25%,transparent);color:var(--texto)}
.tag{display:inline-block;font-size:11px;font-weight:700;color:var(--cor);border:1px solid var(--cor);border-radius:999px;padding:0 6px;margin-top:3px}
.mov-piorou{color:var(--vermelho);font-weight:600}.mov-melhorou{color:var(--verde);font-weight:600}.mov-novo{color:var(--foco)}
.sem-dono{color:var(--suave);font-style:italic}
details.saidas summary{cursor:pointer;font-weight:600}
.causa{margin-top:6px;font-size:13px;line-height:1.45;max-width:62ch}.causa b{color:var(--cor)}
.causa details{margin-top:2px;font-size:12px;color:var(--suave)}.causa summary{cursor:pointer}
.causa ul{margin:4px 0 0;padding-left:18px}
.aviso-ia{font-size:12px;color:var(--suave);margin:-4px 0 8px}
"""


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)).lower()


def _data_br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "—"


def _e(texto) -> str:
    return escape(str(texto), quote=True)


def _area(area: str) -> str:
    return " › ".join(area.split("\\")[1:3]) or area


def _gravidade(l: dict) -> int:
    return CRITICIDADES.index(l["criticidade"])


def _ordenadas(linhas: list[dict]) -> list[dict]:
    """Mais grave primeiro; dentro da criticidade, quem escala e a data mais próxima."""
    return sorted(linhas, key=lambda l: (_gravidade(l), l["escalar"] != "sim", l["data_alvo"] or "9999",
                                         int(l["epic_id"]), CATEGORIAS.index(l["categoria"])))


# --- Blocos ------------------------------------------------------------------------------

def _aviso() -> str:
    if RISCOS_APROVADOS:
        return ""
    return ('<div class="aviso"><b>Uso interno — regras em revisão.</b> O registro é deduzido por regras a partir '
            "dos dados de entrega do ADO (nada é gravado no ADO). Ele vai para a diretoria depois de 2 semanas de "
            "revisão das regras e dos riscos escalados.</div>")


def _kpis(linhas: list[dict]) -> str:
    escalados = [l for l in linhas if l["escalar"] == "sim"]
    epics_escalar = len({l["epic_id"] for l in escalados})
    crit = Counter(l["criticidade"] for l in linhas)
    materializados = sum(l["estado"] == "materializado" for l in linhas)
    cartoes = [("c-escalar", "escalar", "sim", "Escalar", epics_escalar,
                f"Epics com risco para a diretoria ({len(escalados)} riscos)")]
    cartoes += [(f"c-{c}", "criticidade", c, CRITICIDADE[c], crit[c], "riscos") for c in CRITICIDADES]
    cartoes += [("c-materializado", "estado", "materializado", "Materializados", materializados,
                 "riscos de prazo que já aconteceram")]
    return '<div class="kpis">' + "".join(
        f'<button type="button" class="kpi {cls}" data-filtro="{f}" data-valor="{v}" data-rotulo="{_e(rot)}" '
        f'aria-pressed="false"><b>{n}</b><span>{rot}</span><small>{desc}</small></button>'
        for cls, f, v, rot, n, desc in cartoes) + "</div>"


def _reconciliacao(linhas: list[dict]) -> str:
    crit = Counter(l["criticidade"] for l in linhas)
    partes = " + ".join(f"{crit[c]} {CRITICIDADE[c].lower()}" for c in CRITICIDADES)
    epics = len({l["epic_id"] for l in linhas})
    return f'<p class="sub reconc">{len(linhas)} riscos = {partes} · {epics} Epics com pelo menos um risco</p>'


def _causa(narrativa: tuple[str, list[str]] | None) -> str:
    if not narrativa:
        return ""
    texto, fatos = narrativa
    itens = "".join(f"<li>{_e(f)}</li>" for f in fatos)
    return (f'<div class="causa"><b>Causa provável:</b> {_e(texto)}'
            f'<details><summary>fatos usados</summary><ul>{itens}</ul></details></div>')


def _aviso_ia(narrativas: dict) -> str:
    if not narrativas or NARRATIVAS_APROVADAS:
        return ""
    return ('<p class="aviso-ia"><b>Explicação gerada por IA — em validação.</b> A causa provável é redigida por um '
            "modelo de linguagem só a partir dos fatos listados abaixo dela; números e ids são conferidos "
            "automaticamente.</p>")


def _bloco_escalar(linhas: list[dict], narrativas: dict[int, tuple[str, list[str]]]) -> str:
    por_epic: dict[str, list[dict]] = {}
    for l in _ordenadas(l for l in linhas if l["escalar"] == "sim"):
        por_epic.setdefault(l["epic_id"], []).append(l)
    if not por_epic:
        return ('<section class="cartao escalar"><h2>Escalar para a diretoria</h2>'
                '<p class="sub">Nenhum risco disparou um gatilho de escalonamento nesta semana.</p></section>')
    corpo = []
    for epic_id, riscos in por_epic.items():
        l0 = riscos[0]
        gatilhos = sorted({g for r in riscos for g in r["gatilhos"].split("; ") if g}, key=list(GATILHO).index)
        chips = "".join(f'<span class="chip c-{r["criticidade"]}">{CATEGORIA[r["categoria"]]} · '
                        f'{CRITICIDADE[r["criticidade"]]}</span>' for r in riscos)
        dono = _e(l0["dono"]) if l0["dono"] else '<span class="sem-dono">sem dono</span>'
        corpo.append(
            f'<tr class="c-escalar" data-epic="{_e(epic_id)}"><td class="num">{_e(epic_id)}</td>'
            f'<td><div class="tit">{_e(l0["titulo"])}</div><div class="area">{_e(_area(l0["area"]))}</div>'
            f'{_causa(narrativas.get(int(epic_id)))}</td>'
            f'<td class="num">{_data_br(l0["data_alvo"])}</td><td>{dono}</td>'
            f'<td>{"<br>".join(f"<span class=gat>{GATILHO[g]}</span>" for g in gatilhos)}</td><td>{chips}</td>'
            f'<td><button type="button" class="ver" data-filtro="epic" data-valor="{_e(epic_id)}" '
            f'data-rotulo="Epic {_e(epic_id)}" aria-pressed="false">ver riscos</button></td></tr>')
    cab = "".join(f"<th>{c}</th>" for c in ["Epic", "Título", "Data alvo", "Dono", "Por que escalar", "Riscos", ""])
    return (f'<section class="cartao escalar"><h2>Escalar para a diretoria ({len(por_epic)} Epics) '
            '<span class="dica">· o mais grave primeiro</span></h2>' + _aviso_ia(narrativas) +
            f'<div class="tabela"><table><thead><tr>{cab}</tr></thead><tbody>{"".join(corpo)}</tbody></table></div>'
            "</section>")


def _matriz(linhas: list[dict]) -> str:
    from .classificacao import criticidade
    cont = Counter(f'{l["probabilidade"]}-{l["impacto"]}' for l in linhas)
    celulas = ['<span></span>'] + [f'<span class="eixo">impacto {IMPACTO[i].lower()}</span>' for i in IMPACTO]
    for p in PROBABILIDADE:
        celulas.append(f'<span class="eixo">prob. {PROBABILIDADE[p].lower()}</span>')
        for i in IMPACTO:
            n, c = cont[f"{p}-{i}"], criticidade(p, i)
            rotulo = f"prob. {PROBABILIDADE[p].lower()} × impacto {IMPACTO[i].lower()}"
            celulas.append(
                f'<button type="button" class="celula c-{c}{" zero" if not n else ""}" data-filtro="celula" '
                f'data-valor="{p}-{i}" data-rotulo="{_e(rotulo)}" aria-pressed="false" title="{_e(rotulo)}">'
                f"<b>{n}</b><span>{CRITICIDADE[c]}</span></button>")
    return ('<section class="cartao"><h2>Probabilidade × impacto <span class="dica">· clique para filtrar</span></h2>'
            f'<div class="matriz">{"".join(celulas)}</div></section>')


def _grafico_categorias(linhas: list[dict]) -> str:
    por = {c: Counter() for c in CATEGORIAS}
    for l in linhas:
        por[l["categoria"]][l["criticidade"]] += 1
    maior = max((sum(c.values()) for c in por.values()), default=1) or 1
    barras = []
    for cat in CATEGORIAS:
        c = por[cat]
        segs = "".join(f'<i class="c-{k}" style="width:{c[k] / maior:.2%}" title="{c[k]} {CRITICIDADE[k].lower()}"></i>'
                       for k in CRITICIDADES if c[k])
        barras.append(
            f'<button type="button" class="linha-barra" data-filtro="categoria" data-valor="{cat}" '
            f'data-rotulo="{CATEGORIA[cat]}" aria-pressed="false"><span class="rot">{CATEGORIA[cat]}</span>'
            f'<span class="trilho">{segs}</span><span class="tot">{sum(c.values())}</span></button>')
    cores = "".join(f'<span class="c-{k}">{CRITICIDADE[k]}</span>' for k in CRITICIDADES)
    return ('<section class="cartao"><h2>Riscos por categoria <span class="dica">· clique para filtrar</span></h2>'
            f'{"".join(barras)}<div class="cores">{cores}</div></section>')


def _legenda() -> str:
    defs = "".join(f"<dt>{n}</dt><dd>{t}</dd>" for n, t in _DEFINICOES)
    cols = "".join(f"<dt>{n}</dt><dd>{t}</dd>" for n, _, t in _COLUNAS)
    return ('<details class="legenda cartao"><summary>Como ler o registro de riscos</summary>'
            '<p class="sub">Cada linha é um risco: um Epic aberto × uma categoria. O agente deduz os riscos por '
            "regras a partir dos dados de entrega; ninguém precisa cadastrá-los. Criticidade = probabilidade × "
            f"impacto.</p><dl>{defs}{cols}</dl></details>")


def _ferramentas(linhas: list[dict]) -> str:
    programas = sorted({l["programa"] for l in linhas})
    op_prog = "".join(f'<option value="{_e(p)}">{_e(p)}</option>' for p in programas)
    op_cat = "".join(f'<option value="{c}">{CATEGORIA[c]}</option>' for c in CATEGORIAS)
    return ('<div class="ferramentas so-js">'
            '<input class="f-busca" type="search" placeholder="Buscar por id, título, área, evidência ou dono" '
            'aria-label="Buscar riscos">'
            f'<select data-filtro-sel="categoria" aria-label="Filtrar por categoria"><option value="">Todas as categorias</option>{op_cat}</select>'
            f'<select data-filtro-sel="programa" aria-label="Filtrar por programa"><option value="">Todos os programas</option>{op_prog}</select>'
            '<span class="contador" aria-live="polite"></span>'
            '<button type="button" class="limpar" hidden>Limpar filtros</button></div>')


def _linha(l: dict) -> str:
    crit = l["criticidade"]
    escala = l["escalar"] == "sim"
    gatilhos = [GATILHO[g] for g in l["gatilhos"].split("; ") if g]
    tag = (f'<div><span class="tag c-escalar" title="{_e("; ".join(gatilhos))}">Escalar</span></div>'
           if escala else "")
    categoria = CATEGORIA[l["categoria"]] + (' <span class="tag c-materializado">materializado</span>'
                                              if l["estado"] == "materializado" else "")
    chips = "".join(f'<span class="chip">{_e(ev.strip())}</span>' for ev in l["evidencia"].split("; ") if ev.strip())
    dono = _e(l["dono"]) if l["dono"] else '<span class="sem-dono">sem dono</span>'
    mov = l["movimento"]
    antes = l["criticidade_anterior"]
    mov_txt = MOVIMENTO[mov] + (f" (era {CRITICIDADE[antes]})" if antes and antes != crit else "")
    busca = _sem_acento(f'{l["epic_id"]} {l["titulo"]} {l["area"]} {l["evidencia"]} {l["dono"]} '
                        f'{CATEGORIA[l["categoria"]]}')
    celulas = [
        f'<td data-v="{_gravidade(l)}"><span class="selo c-{crit}">{CRITICIDADE[crit]}</span>{tag}</td>',
        f'<td class="num" data-v="{_e(l["epic_id"])}">{_e(l["epic_id"])}</td>',
        f'<td class="titulo" data-v="{_e(l["titulo"])}"><div class="tit">{_e(l["titulo"])}</div>'
        f'<div class="area">{_e(_area(l["area"]))}</div></td>',
        f'<td data-v="{CATEGORIAS.index(l["categoria"])}">{categoria}</td>',
        f'<td data-v="{list(PROBABILIDADE).index(l["probabilidade"])}">{PROBABILIDADE[l["probabilidade"]]}</td>',
        f'<td data-v="{list(IMPACTO).index(l["impacto"])}">{IMPACTO[l["impacto"]]}</td>',
        f'<td class="motivos" data-v="{_e(l["evidencia"])}">{chips}</td>',
        f'<td data-v="{_e(l["dono"])}">{dono}</td>',
        f'<td class="num" data-v="{_e(l["data_alvo"])}">{_data_br(l["data_alvo"])}</td>',
        f'<td data-v="{list(MOVIMENTO).index(mov)}" class="mov-{mov}">{mov_txt}</td>',
    ]
    return (f'<tr class="c-{crit}" data-risco="{_e(l["risco_id"])}" data-criticidade="{crit}" '
            f'data-categoria="{l["categoria"]}" data-programa="{_e(l["programa"])}" '
            f'data-celula="{l["probabilidade"]}-{l["impacto"]}" data-escalar="{l["escalar"]}" '
            f'data-estado="{l["estado"]}" data-epic="{_e(l["epic_id"])}" data-busca="{_e(busca)}">'
            + "".join(celulas) + "</tr>")


def _tabela(linhas: list[dict]) -> str:
    cab = "".join(f'<th data-tipo="{tipo}" title="{_e(texto)}" scope="col"><button type="button">{nome}</button></th>'
                  for nome, tipo, texto in _COLUNAS)
    corpo = "".join(_linha(l) for l in _ordenadas(linhas))
    vazio = f'<tr class="vazio" hidden><td colspan="{len(_COLUNAS)}">Nenhum risco com esses filtros.</td></tr>'
    return (f'<div class="tabela"><table class="dados"><thead><tr>{cab}</tr></thead>'
            f"<tbody>{corpo}{vazio}</tbody></table></div>")


def _saidas(saidas: list[dict], anterior: date | None) -> str:
    if anterior is None:
        return ""
    desde = anterior.strftime("%d/%m/%Y")
    if not saidas:
        return f'<p class="sub">Nenhum risco saiu do registro desde {desde}.</p>'
    linhas = "".join(
        f'<tr><td>{_e(s["risco_id"])}</td><td>{_e(s.get("titulo", ""))}</td>'
        f'<td>{CATEGORIA.get(s.get("categoria", ""), _e(s.get("categoria", "")))}</td>'
        f'<td>{CRITICIDADE.get(s.get("criticidade", ""), "—")}</td><td>{_e(s["motivo_saida"])}</td></tr>'
        for s in sorted(saidas, key=lambda s: s["risco_id"]))
    cab = "".join(f"<th>{c}</th>" for c in ["Risco", "Título", "Categoria", "Criticidade anterior", "Motivo"])
    return (f'<details class="saidas cartao"><summary>Saíram do registro desde {desde} ({len(saidas)})</summary>'
            f'<div class="tabela"><table><thead><tr>{cab}</tr></thead><tbody>{linhas}</tbody></table></div></details>')


def gerar_aba(linhas: list[dict], saidas: list[dict], anterior: date | None,
              narrativas: dict[int, tuple[str, list[str]]] | None = None, leitura: bool = False) -> str:
    """Miolo da aba Riscos. `linhas` = linhas do registro (CSV); `anterior` = data do registro comparado;
    `narrativas` = epic_id → (causa provável com nomes reais, fatos usados), só para o bloco Escalar."""
    caixa = ('<section class="cartao leitura" data-aba="riscos" aria-live="polite" hidden></section>'
             if leitura else "")
    return (_aviso() + _kpis(linhas) + caixa + _reconciliacao(linhas) + _bloco_escalar(linhas, narrativas or {})
            + f'<div class="paineis">{_grafico_categorias(linhas)}{_matriz(linhas)}</div>'
            + _legenda() + _ferramentas(linhas) + _tabela(linhas) + _saidas(saidas, anterior))
