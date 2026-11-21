"""Impacto do Epic, criticidade do risco (matriz probabilidade × impacto) e gatilhos de Escalar.

Não há campo de valor de negócio confiável no ADO (area_valor e prioridade são iguais em quase
todos os Epics); por isso o impacto mede tamanho (itens restantes) e quantos Epics dependem dele.
"""
from datetime import date, timedelta

from radar.dados import Dados, Item

from .regras import Sinal

RESTANTE_ALTO, RESTANTE_MEDIO = 30, 10   # confirmados no planejamento (mediana 7, p75 22, p90 49)
JANELA_DATA_PROXIMA = timedelta(days=28)
ATRASO_GRANDE = timedelta(weeks=8)

CRITICIDADES = ("critico", "alto", "medio", "baixo")   # da mais para a menos grave
_MATRIZ = {
    ("alta", "alto"): "critico", ("alta", "medio"): "alto", ("alta", "baixo"): "medio",
    ("media", "alto"): "alto", ("media", "medio"): "medio", ("media", "baixo"): "baixo",
}
GATILHOS = ("data_proxima", "dependencia_entre_programas", "atraso_grande", "sem_dono")


def dependentes(dados: Dados) -> dict[int, int]:
    """Epic -> nº de Epics distintos que dependem de algum item dele."""
    por_epic: dict[int, set[int]] = {}
    for p, s in dados.dependencias:
        if (epic_p := dados.epic_de.get(p.id)) is not None:
            por_epic.setdefault(epic_p, set()).add(dados.epic_de[s.id])
    return {e: len(v) for e, v in por_epic.items()}


def impacto(restante: int, n_dependentes: int, escopo_vazio: bool) -> str:
    if restante >= RESTANTE_ALTO or n_dependentes >= 2:
        return "alto"
    if restante >= RESTANTE_MEDIO or n_dependentes == 1 or escopo_vazio:
        return "medio"   # escopo vazio: tamanho desconhecido, não dá para chamar de baixo
    return "baixo"


def criticidade(probabilidade: str, impacto_: str) -> str:
    return _MATRIZ[(probabilidade, impacto_)]


def gatilhos(sinal: Sinal, epic: Item, criticidade_: str, hoje: date) -> tuple[str, ...]:
    """Gatilhos de Escalar que o risco dispara, na ordem de GATILHOS (vazio = não escala)."""
    critico = criticidade_ == "critico"
    disparados = {
        "data_proxima": critico and epic.alvo is not None and hoje <= epic.alvo <= hoje + JANELA_DATA_PROXIMA,
        "dependencia_entre_programas": (sinal.categoria == "DEPENDENCIA" and sinal.probabilidade == "alta"
                                        and sinal.entre_programas),
        "atraso_grande": sinal.estado == "materializado" and epic.alvo is not None and epic.alvo < hoje - ATRASO_GRANDE,
        "sem_dono": critico and not epic.responsavel,
    }
    return tuple(g for g in GATILHOS if disparados[g])
