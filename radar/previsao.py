"""Previsão por Epic: ritmo semanal, Monte Carlo e farol.

`prever()` só enxerga o que existia antes de `hoje`: itens criados antes e
concluídos antes. Por isso o backtest chama a mesma função com hoje = data de
corte, e o relatório e o backtest testam exatamente o mesmo código.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from .dados import Item

# Congelado para o teste prospectivo: qualquer mudança no modelo exige nova versão.
MODELO_VERSAO = "v3"
INICIO_RITMO = date(2026, 3, 2)  # fevereiro/2026 foi migração: fechamentos em massa
SEMANAS_RITMO = 12
CORTES_FAROL = (0.40, 0.70)


@dataclass(frozen=True)
class Previsao:
    epic_id: int
    secao: str  # "vermelho" | "amarelo" | "verde" | "ja_atrasado" | "sem_como_prever"
    escopo: int
    concluidos: int
    restante: int
    ritmo_medio: float
    entrada_media: float
    prob_cumprir: float | None
    p50: date | None
    p85: date | None
    razao_ritmo: float | None


def _concluido(it: Item, hoje: date) -> bool:
    return it.estado == "Done" and it.fechado is not None and it.fechado < hoje


def _por_semana(datas: list[date], hoje: date) -> np.ndarray:
    """Contagem por semana (segunda a domingo) nas últimas semanas completas antes de `hoje`."""
    semana_atual = hoje - timedelta(days=hoje.weekday())
    inicios = [semana_atual - timedelta(weeks=k) for k in range(SEMANAS_RITMO, 0, -1)]
    contagem = {s: 0 for s in inicios if s >= INICIO_RITMO}
    for d in datas:
        s = d - timedelta(days=d.weekday())
        if s in contagem:
            contagem[s] += 1
    return np.array(list(contagem.values()), dtype=int)


def ritmo_semanal(itens: list[Item], hoje: date) -> np.ndarray:
    return _por_semana([it.fechado for it in itens if _concluido(it, hoje)], hoje)


def entrada_semanal(itens: list[Item], hoje: date) -> np.ndarray:
    return _por_semana([it.criado for it in itens if it.criado < hoje], hoje)


def simular(ritmo: np.ndarray, restante: int, rng: np.random.Generator,
            entrada: np.ndarray | None = None, semanas_alvo: int = 0,
            execucoes: int = 10_000, max_semanas: int = 520) -> np.ndarray:
    """Semanas necessárias para zerar o trabalho em cada execução (inf se não termina em max_semanas).

    Cada semana simulada sorteia uma semana do histórico e usa o par (entregues, criados)
    dela: semanas de planejamento costumam ter as duas coisas juntas. Itens novos só
    entram até `semanas_alvo`; o que é criado depois da data alvo não conta para ela.
    """
    if restante <= 0:
        return np.zeros(execucoes)
    if entrada is None:
        entrada = np.zeros_like(ritmo)
    semanas = np.full(execucoes, np.inf)
    acumulado = np.zeros(execucoes)
    bloco_tam = 52
    for offset in range(0, max_semanas, bloco_tam):
        idx = rng.integers(0, len(ritmo), size=(execucoes, bloco_tam))
        semana = offset + np.arange(1, bloco_tam + 1)
        saldo = ritmo[idx] - np.where(semana <= semanas_alvo, entrada[idx], 0)
        soma = acumulado[:, None] + saldo.cumsum(axis=1)
        terminou = soma >= restante
        novos = np.isinf(semanas) & terminou.any(axis=1)
        semanas[novos] = offset + terminou[novos].argmax(axis=1) + 1
        if not np.isinf(semanas).any():
            break
        acumulado = soma[:, -1]
    return semanas


def razao_ritmo(restante: int, ritmo_medio: float, entrada_media: float, dias_ate_alvo: int) -> float | None:
    """Quantas vezes o ritmo atual precisa crescer para zerar o trabalho até a data alvo.

    Conta a entrada esperada de itens novos até lá. None quando não há ritmo para comparar.
    """
    if not ritmo_medio:
        return None
    # Data alvo nesta semana: o ritmo necessário é o trabalho inteiro em uma semana.
    semanas_ate_alvo = max(dias_ate_alvo / 7, 1)
    necessario = (restante + entrada_media * semanas_ate_alvo) / semanas_ate_alvo
    return necessario / ritmo_medio


def classificar_farol(prob: float, cortes: tuple[float, float] = CORTES_FAROL) -> str:
    if prob < cortes[0]:
        return "vermelho"
    return "amarelo" if prob < cortes[1] else "verde"


def _data_em(hoje: date, semanas: float) -> date | None:
    return None if math.isinf(semanas) else hoje + timedelta(weeks=int(semanas))


def prever(epic: Item, itens: list[Item], hoje: date, rng: np.random.Generator,
           cortes: tuple[float, float] = CORTES_FAROL) -> Previsao:
    existentes = [it for it in itens if it.criado < hoje]
    concluidos = sum(_concluido(it, hoje) for it in existentes)
    restante = len(existentes) - concluidos
    ritmo = ritmo_semanal(existentes, hoje)
    entrada = entrada_semanal(existentes, hoje)
    media = float(ritmo.mean()) if ritmo.size else 0.0
    media_entrada = float(entrada.mean()) if entrada.size else 0.0
    base = dict(epic_id=epic.id, escopo=len(existentes), concluidos=concluidos, restante=restante,
                ritmo_medio=media, entrada_media=media_entrada, prob_cumprir=None, p50=None, p85=None,
                razao_ritmo=None)

    if epic.alvo is not None and epic.alvo < hoje:
        return Previsao(secao="ja_atrasado", **base)
    if epic.alvo is None:
        return Previsao(secao="sem_como_prever", **base)
    if not existentes:
        # Data marcada sem nenhum item detalhado: no backtest, todos esses atrasaram.
        return Previsao(secao="vermelho", **base)
    if restante > 0 and media == 0:
        return Previsao(secao="sem_como_prever", **base)

    dias = (epic.alvo - hoje).days
    semanas = simular(ritmo, restante, rng, entrada=entrada, semanas_alvo=dias // 7)
    prob = float(np.mean(semanas * 7 <= dias))
    p50, p85 = np.quantile(semanas, [0.50, 0.85], method="higher")
    razao = razao_ritmo(restante, media, media_entrada, dias)
    return Previsao(**{**base, "prob_cumprir": prob, "p50": _data_em(hoje, p50),
                       "p85": _data_em(hoje, p85), "razao_ritmo": razao},
                    secao=classificar_farol(prob, cortes))
