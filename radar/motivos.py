"""Motivos por regra para os Epics vermelhos e amarelos.

Frases curtas e com números, para o executivo entender o porquê sem abrir o ADO.
Nenhum LLM aqui: as frases saem só das regras da spec.
"""
from datetime import date, timedelta

from .dados import Item
from .previsao import Previsao

JANELA_RECENTE = timedelta(weeks=4)
MIN_ITENS_CRESCIMENTO = 5        # Epic com menos itens há 4 semanas está sendo detalhado, não crescendo
CRESCIMENTO_EXIBIDO_MAX = 3.0    # acima de +300%, o texto diz "mais que quadruplicou"


def crescimento_escopo(existentes: list[Item], hoje: date) -> tuple[float, int] | None:
    """(crescimento, novos) contra o escopo de 4 semanas atrás; None se havia menos de 5 itens.

    Regra única do Radar e dos Riscos (alinhada em 2026-11-11: antes o Radar dividia pelo escopo atual).
    """
    antes = sum(i.criado < hoje - JANELA_RECENTE for i in existentes)
    if antes < MIN_ITENS_CRESCIMENTO:
        return None
    novos = len(existentes) - antes
    return novos / antes, novos


def texto_crescimento(crescimento: float, novos: int) -> str:
    if crescimento > CRESCIMENTO_EXIBIDO_MAX:
        return f"escopo mais que quadruplicou nas últimas 4 semanas (+{novos} itens)"
    return f"escopo cresceu {crescimento:.0%} nas últimas 4 semanas (+{novos} itens)"


def _decimal(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def motivos(p: Previsao, itens: list[Item], features: list[Item], hoje: date) -> list[str]:
    if p.secao not in ("vermelho", "amarelo"):
        return []
    if p.escopo == 0:
        return ["data marcada sem nenhum item detalhado"]

    existentes = [i for i in itens if i.criado < hoje]
    entregues = [i.fechado for i in existentes if i.estado == "Done" and i.fechado and i.fechado < hoje]
    restantes = [i for i in existentes if not (i.estado == "Done" and i.fechado and i.fechado < hoje)]
    lista = []

    if p.razao_ritmo is not None and p.razao_ritmo >= 1.5:
        lista.append(f"precisa entregar {_decimal(p.razao_ritmo)}× mais rápido")

    if restantes:
        if not entregues:
            lista.append("nenhuma entrega registrada")
        elif (dias := (hoje - max(entregues)).days) >= JANELA_RECENTE.days:
            lista.append(f"sem entregas há {dias // 7} semanas")

    if (c := crescimento_escopo(existentes, hoje)) and c[0] >= 0.20:
        lista.append(texto_crescimento(*c))

    sem_dono = sum(not i.responsavel for i in restantes)
    if restantes and sem_dono / len(restantes) >= 0.20:
        lista.append(f"{sem_dono} de {len(restantes)} itens restantes sem responsável")

    vencidas = sum(f.estado not in ("Done", "Removed") and f.alvo is not None and f.alvo < hoje for f in features)
    if vencidas:
        lista.append(f"{vencidas} Feature{'s' if vencidas > 1 else ''} com data alvo vencida")
    return lista
