"""Registro sintético de riscos: um `Risco` por Epic × categoria, com id estável.

O CSV semanal (`riscos-AAAA-MM-DD.csv`) é o próprio registro e o seu histórico: o
movimento (novo, piorou, melhorou, igual) e os riscos que saíram vêm da comparação
com o CSV anterior mais recente.
"""
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from radar.dados import Dados

from .classificacao import CRITICIDADES, criticidade, dependentes, gatilhos, impacto
from .regras import avaliar, contexto, programa

REGRAS_VERSAO = "r1"
COLUNAS = ["regras_versao", "data", "risco_id", "epic_id", "titulo", "programa", "area", "categoria",
           "estado", "probabilidade", "impacto", "criticidade", "evidencia", "dono", "data_alvo",
           "escalar", "gatilhos", "movimento", "criticidade_anterior"]


@dataclass(frozen=True)
class Risco:
    id: str                 # "R-90006-PRAZO"
    epic_id: int
    categoria: str
    estado: str             # "aberto" | "materializado"
    probabilidade: str      # "alta" | "media"
    impacto: str            # "alto" | "medio" | "baixo"
    criticidade: str        # "critico" | "alto" | "medio" | "baixo"
    evidencias: tuple[str, ...]
    gatilhos: tuple[str, ...]   # vazio = não escala


def risco_id(epic_id: int, categoria: str) -> str:
    return f"R-{epic_id}-{categoria}"


def montar(dados: Dados, hoje: date) -> list[Risco]:
    """Todos os riscos dos Epics abertos, ordenados por Epic e categoria."""
    n_dependentes = dependentes(dados)
    riscos = []
    for epic_id, sinais in sorted(avaliar(dados, hoje).items()):
        epic = dados.epics[epic_id]
        c = contexto(epic, dados, hoje)
        imp = impacto(len(c.restantes), n_dependentes.get(epic_id, 0), escopo_vazio=not c.existentes)
        for s in sinais:
            crit = criticidade(s.probabilidade, imp)
            riscos.append(Risco(id=risco_id(epic_id, s.categoria), epic_id=epic_id, categoria=s.categoria,
                                estado=s.estado, probabilidade=s.probabilidade, impacto=imp, criticidade=crit,
                                evidencias=s.evidencias, gatilhos=gatilhos(s, epic, crit, hoje)))
    return riscos


# --- Histórico -------------------------------------------------------------------------

def csv_anterior(pasta: Path, hoje: date) -> Path | None:
    """O `riscos-AAAA-MM-DD.csv` mais recente com data anterior a `hoje`."""
    datados = []
    for p in pasta.glob("riscos-*.csv"):
        try:
            datados.append((date.fromisoformat(p.stem.removeprefix("riscos-")), p))
        except ValueError:
            continue
    anteriores = [x for x in datados if x[0] < hoje]
    return max(anteriores)[1] if anteriores else None


def ler_csv(caminho: Path | None) -> list[dict]:
    if caminho is None:
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def movimento(r: Risco, anterior: dict | None) -> str:
    if anterior is None:
        return "novo"
    grav_antes = CRITICIDADES.index(anterior["criticidade"])
    grav_agora = CRITICIDADES.index(r.criticidade)
    if grav_agora < grav_antes or (r.estado == "materializado" and anterior["estado"] == "aberto"):
        return "piorou"
    if grav_agora > grav_antes or (r.estado == "aberto" and anterior["estado"] == "materializado"):
        return "melhorou"
    return "igual"


def saidas(riscos: list[Risco], anteriores: list[dict], dados: Dados) -> list[dict]:
    """Riscos do CSV anterior que não estão mais no registro, com o motivo."""
    atuais = {r.id for r in riscos}
    resultado = []
    for a in anteriores:
        if a["risco_id"] in atuais:
            continue
        epic = dados.epics.get(int(a["epic_id"]))
        fechado = epic is None or epic.estado in ("Done", "Removed")
        resultado.append({**a, "motivo_saida": "Epic fechado" if fechado else "sinal desapareceu"})
    return resultado


# --- Linhas do CSV ---------------------------------------------------------------------

def linhas_csv(riscos: list[Risco], dados: Dados, hoje: date, anteriores: list[dict]) -> list[dict]:
    por_id = {a["risco_id"]: a for a in anteriores}
    linhas = []
    for r in riscos:
        e = dados.epics[r.epic_id]
        ant = por_id.get(r.id)
        linhas.append({
            "regras_versao": REGRAS_VERSAO, "data": hoje.isoformat(), "risco_id": r.id, "epic_id": r.epic_id,
            "titulo": e.titulo, "programa": programa(e.area), "area": e.area, "categoria": r.categoria,
            "estado": r.estado, "probabilidade": r.probabilidade, "impacto": r.impacto,
            "criticidade": r.criticidade, "evidencia": "; ".join(r.evidencias), "dono": e.responsavel,
            "data_alvo": e.alvo.isoformat() if e.alvo else "", "escalar": "sim" if r.gatilhos else "nao",
            "gatilhos": "; ".join(r.gatilhos), "movimento": movimento(r, ant),
            "criticidade_anterior": ant["criticidade"] if ant else "",
        })
    return linhas

