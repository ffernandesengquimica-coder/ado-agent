"""Backtest: o modelo teria acertado se tivesse rodado em datas passadas?

Para cada data de corte, prevê os Epics que estavam abertos e cuja data alvo já
passou hoje (então sabemos se cumpriram), e compara o modelo com dois baselines:
    ingenuo  -> atrasa se o % concluído < % do tempo decorrido até a data alvo
    trivial  -> todos atrasam (com taxa base alta, esse "modelo" parece bom)

Verdade pela entrega: todo o escopo criado até a data alvo concluído até ela.
Limitações aceitas na spec: usa a data alvo atual (não há histórico de datas) e
itens Removed depois do corte somem da reconstrução.
"""
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np

from .dados import Dados, Item
from .previsao import MODELO_VERSAO, prever


@dataclass(frozen=True)
class Metricas:
    n: int
    vp: int
    fp: int
    fn: int
    precisao: float
    recall: float
    f1: float
    taxa_base: float


@dataclass(frozen=True)
class Resultado:
    linhas: list[dict]   # métricas por corte/preditor (+ "agregado")
    detalhe: list[dict]  # uma linha por (corte, Epic)
    passou: bool


def atrasou(epic: Item, escopo: list[Item]) -> bool | None:
    """Verdade pela entrega: todo o escopo criado até a data alvo foi concluído até ela?

    O estado do Epic não importa: fechá-lo no ADO é burocracia e costuma vir dias
    ou semanas depois da entrega. None quando não há escopo na data alvo.
    """
    na_data = [i for i in escopo if i.criado <= epic.alvo]
    if not na_data:
        return None
    return not all(i.estado == "Done" and i.fechado and i.fechado <= epic.alvo for i in na_data)


def avaliaveis(epics: dict[int, Item], corte: date, hoje: date) -> list[Item]:
    return [
        e for e in epics.values()
        if e.estado != "Removed"
        and e.criado < corte
        and not (e.fechado and e.fechado < corte)
        and e.alvo is not None and corte <= e.alvo < hoje
    ]


def ingenuo_preve_atraso(epic: Item, concluidos: int, escopo: int, corte: date) -> bool:
    inicio = epic.inicio if epic.inicio and epic.inicio < epic.alvo else epic.criado
    duracao = max((epic.alvo - inicio).days, 1)
    decorrido = min(max((corte - inicio).days / duracao, 0.0), 1.0)
    progresso = concluidos / escopo if escopo else 0.0
    return progresso < decorrido


def metricas(previsto: list[bool], real: list[bool]) -> Metricas:
    vp = sum(p and r for p, r in zip(previsto, real))
    fp = sum(p and not r for p, r in zip(previsto, real))
    fn = sum(r and not p for p, r in zip(previsto, real))
    precisao = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
    n = len(real)
    return Metricas(n=n, vp=vp, fp=fp, fn=fn, precisao=precisao, recall=recall, f1=f1,
                    taxa_base=sum(real) / n if n else 0.0)


def passou_portao(modelo: Metricas, ingenuo: Metricas, trivial: Metricas) -> bool:
    return (modelo.recall >= 0.70
            and modelo.precisao >= modelo.taxa_base + 0.10
            and modelo.f1 > ingenuo.f1
            and modelo.f1 > trivial.f1)


def executar(dados: Dados, cortes: list[date], hoje: date, semente: int = 42) -> Resultado:
    rng = np.random.default_rng(semente)
    detalhe = []
    for corte in cortes:
        for e in sorted(avaliaveis(dados.epics, corte, hoje), key=lambda e: e.id):
            escopo = dados.escopo.get(e.id, [])
            verdade = atrasou(e, escopo)
            if verdade is None:
                continue
            p = prever(e, escopo, corte, rng)
            detalhe.append({
                "modelo_versao": MODELO_VERSAO, "corte": corte.isoformat(), "epic_id": e.id,
                "data_alvo": e.alvo.isoformat(),
                "secao": p.secao, "prob_cumprir": p.prob_cumprir, "escopo": p.escopo,
                "restante": p.restante, "ritmo_medio": p.ritmo_medio, "entrada_media": p.entrada_media,
                "modelo": p.secao == "vermelho",
                "ingenuo": ingenuo_preve_atraso(e, p.concluidos, p.escopo, corte),
                "trivial": True,
                "atrasou": verdade,
            })

    linhas, agregadas = [], {}
    grupos = [(c.isoformat(), [d for d in detalhe if d["corte"] == c.isoformat()]) for c in cortes]
    for nome, ds in grupos + [("agregado", detalhe)]:
        for preditor in ("modelo", "ingenuo", "trivial"):
            m = metricas([d[preditor] for d in ds], [d["atrasou"] for d in ds])
            linhas.append({"modelo_versao": MODELO_VERSAO, "corte": nome, "preditor": preditor,
                           "epics_unicos": len({d["epic_id"] for d in ds}), **asdict(m)})
            if nome == "agregado":
                agregadas[preditor] = m
    return Resultado(linhas=linhas, detalhe=detalhe,
                     passou=passou_portao(agregadas["modelo"], agregadas["ingenuo"], agregadas["trivial"]))
