"""Fatos de um recorte do painel: o painel inteiro, um programa ou uma categoria de risco.

São contagens das linhas do registro de riscos e do Radar, mais os 3 Epics mais graves do recorte
com as evidências. Nada de nome de pessoa: os donos não entram nos fatos de recorte.
"""
from collections import Counter
from datetime import date

from .fatos import CATEGORIA, CRITICIDADE, SECAO, _data, por_epic

ORDEM_CRITICIDADE = ["critico", "alto", "medio", "baixo"]
MOVIMENTO = {"novo": "novos", "piorou": "pioraram", "melhorou": "melhoraram"}
ORDEM_SECOES = ["vermelho", "amarelo", "ja_atrasado", "sem_como_prever", "verde"]
MAX_EPICS = 3


def programa(area: str) -> str:
    """2º nível da área; um item na raiz do projeto conta como programa com o nome do projeto (mesma regra do Radar e dos Riscos)."""
    partes = area.split("\\")
    return partes[1] if len(partes) > 1 else area


def gravidade(l: dict) -> tuple:
    """Ordem do mais grave: materializado, criticidade, Escalar, data alvo mais próxima."""
    return (l["estado"] != "materializado", ORDEM_CRITICIDADE.index(l["criticidade"]), l["escalar"] != "sim",
            l["data_alvo"] or "9999")


def _contagem(rotulos: dict, valores) -> dict:
    c = Counter(valores)
    return {rotulos[k]: c[k] for k in rotulos if c[k]}


def _epics_mais_graves(riscos: list[dict]) -> list[dict]:
    grupos = por_epic(riscos)
    ordem = sorted(grupos, key=lambda e: min(gravidade(r) for r in grupos[e]))
    saida = []
    for e in ordem[:MAX_EPICS]:
        rs = sorted(grupos[e], key=gravidade)
        saida.append({"epic": f"#{e}", "titulo": rs[0]["titulo"], "programa": rs[0]["programa"],
                      "data_alvo": _data(rs[0]["data_alvo"]),
                      "riscos": [f"{CATEGORIA[r['categoria']]} ({CRITICIDADE[r['criticidade']]}"
                                 f"{', escalar' if r['escalar'] == 'sim' else ''}): {r['evidencia']}" for r in rs]})
    return saida


def fatos_recorte(linhas_radar: list[dict], linhas_riscos: list[dict], hoje: date,
                  programa_: str | None = None, categoria: str | None = None) -> tuple[dict, bool]:
    """(fatos, usa_radar). Sem programa nem categoria = o painel inteiro."""
    riscos = [l for l in linhas_riscos
              if (programa_ is None or l["programa"] == programa_) and (categoria is None or l["categoria"] == categoria)]
    epics = {int(l["epic_id"]) for l in riscos}
    if programa_ is not None:
        radar = [l for l in linhas_radar if programa(l["area"]) == programa_]
    elif categoria is not None:
        radar = [l for l in linhas_radar if int(l["epic_id"]) in epics]
    else:
        radar = list(linhas_radar)
    escalar = [l for l in riscos if l["escalar"] == "sim"]
    nome = (f"programa {programa_}" if programa_ else f"categoria {CATEGORIA[categoria]}" if categoria
            else "painel inteiro do projeto")
    f = {
        "hoje": _data(hoje.isoformat()),
        "recorte": nome,
        "riscos": len(riscos),
        "epics_com_risco": len(epics),
        "riscos_por_criticidade": _contagem(CRITICIDADE, (l["criticidade"] for l in riscos)),
        "epics_no_escalar": len({l["epic_id"] for l in escalar}),
        "riscos_de_prazo_materializados": sum(l["estado"] == "materializado" for l in riscos),
        "movimento_desde_o_registro_anterior": (_contagem(MOVIMENTO, (l["movimento"] for l in riscos))
                                                or "sem mudanças"),
        "epics_mais_graves": _epics_mais_graves(riscos),
    }
    if categoria is None:
        f["riscos_por_categoria"] = _contagem(CATEGORIA, (l["categoria"] for l in riscos))
    if programa_ is None:
        top = Counter(l["programa"] for l in riscos).most_common(5)
        f["programas_com_mais_riscos"] = {p: n for p, n in top}
    if radar:
        f["radar_epics_abertos_por_situacao"] = _contagem({s: SECAO[s] for s in ORDEM_SECOES},
                                                          (l["secao"] for l in radar))
    return {k: v for k, v in f.items() if v not in ("", [], {}, None)}, bool(radar)


def recortes(linhas_riscos: list[dict]) -> list[tuple[str, str | None, str | None]]:
    """(alvo, programa, categoria): o geral, cada programa e cada categoria presentes no registro."""
    programas = sorted({l["programa"] for l in linhas_riscos})
    categorias = [c for c in CATEGORIA if any(l["categoria"] == c for l in linhas_riscos)]
    return ([("geral", None, None)] + [(f"programa:{p}", p, None) for p in programas]
            + [(f"categoria:{c}", None, c) for c in categorias])
