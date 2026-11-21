from datetime import date, timedelta

import numpy as np
import pytest

from radar.dados import Item
from radar.previsao import classificar_farol, entrada_semanal, prever, ritmo_semanal, simular

HOJE = date(2026, 11, 5)  # quinta; semana atual começa em 02/11


def it(id, *, criado=date(2026, 3, 2), fechado=None, estado=None, alvo=None, tipo="Product Backlog Item"):
    estado = estado or ("Done" if fechado else "New")
    return Item(id=id, tipo=tipo, titulo=f"{tipo} {id}", estado=estado, area="Atlas\\A", responsavel="P",
                criado=criado, fechado=fechado, inicio=None, alvo=alvo)


def epic(alvo=None, criado=date(2026, 3, 2)):
    return it(1, tipo="Epic", alvo=alvo, criado=criado)


def fechados_por_semana(por_semana: list[int], ultima_segunda: date, id0=100) -> list[Item]:
    """Itens Done distribuídos nas semanas que terminam em `ultima_segunda` (a última da lista)."""
    itens, n = [], id0
    for k, qtd in enumerate(reversed(por_semana)):
        segunda = ultima_segunda - timedelta(weeks=k)
        for _ in range(qtd):
            itens.append(it(n, fechado=segunda + timedelta(days=2)))
            n += 1
    return itens


# --- ritmo -------------------------------------------------------------------

def test_ritmo_usa_12_semanas_completas_antes_da_semana_atual():
    itens = fechados_por_semana([1] * 12, ultima_segunda=date(2026, 10, 26))
    itens.append(it(999, fechado=date(2026, 11, 3)))  # semana atual: fora
    r = ritmo_semanal(itens, HOJE)
    assert r.tolist() == [1] * 12


def test_ritmo_inclui_semanas_sem_entrega_como_zero():
    itens = fechados_por_semana([0, 3, 0, 0, 2, 0, 0, 0, 0, 0, 0, 1], ultima_segunda=date(2026, 10, 26))
    assert ritmo_semanal(itens, HOJE).tolist() == [0, 3, 0, 0, 2, 0, 0, 0, 0, 0, 0, 1]


def test_ritmo_nunca_usa_semanas_antes_de_marco():
    # Em 06/04 só existem 5 semanas completas desde 02/03 (fevereiro = migração).
    itens = [it(1, criado=date(2026, 1, 20), fechado=date(2026, 2, 10)), it(2, fechado=date(2026, 3, 4))]
    r = ritmo_semanal(itens, date(2026, 4, 6))
    assert r.tolist() == [1, 0, 0, 0, 0]


def test_ritmo_ignora_itens_nao_done():
    itens = [it(1, fechado=date(2026, 10, 28), estado="Removed")]
    assert ritmo_semanal(itens, HOJE).sum() == 0


# --- entrada (crescimento de escopo) ---------------------------------------------

def test_entrada_conta_criacoes_por_semana_na_mesma_janela():
    itens = [it(1, criado=date(2026, 10, 28)), it(2, criado=date(2026, 10, 29), fechado=date(2026, 10, 30)),
             it(3, criado=date(2026, 8, 12)), it(4, criado=date(2026, 11, 3))]  # 4: semana atual, fora
    assert entrada_semanal(itens, HOJE).tolist() == [1] + [0] * 10 + [2]


def test_entrada_nunca_usa_semanas_antes_de_marco():
    itens = [it(1, criado=date(2026, 2, 10)), it(2, criado=date(2026, 3, 3))]
    assert entrada_semanal(itens, date(2026, 4, 6)).tolist() == [1, 0, 0, 0, 0]


# --- simulação -----------------------------------------------------------------

def test_simular_com_ritmo_constante_e_exato():
    s = simular(np.array([2, 2, 2]), restante=10, rng=np.random.default_rng(0), execucoes=100)
    assert (s == 5).all()


def test_simular_ritmo_zero_nunca_termina():
    s = simular(np.array([0, 0]), restante=3, rng=np.random.default_rng(0), execucoes=10)
    assert np.isinf(s).all()


def test_simular_com_entrada_usa_o_saldo_semanal():
    # entrega 3, entra 1 → saldo 2/semana; 10 restantes → 5 semanas
    s = simular(np.array([3, 3]), 10, np.random.default_rng(0), entrada=np.array([1, 1]),
                semanas_alvo=52, execucoes=50)
    assert (s == 5).all()


def test_simular_para_de_somar_entrada_depois_da_data_alvo():
    # entrega 2, entra 2, alvo em 3 semanas: entram 6 no total; 2k >= 4 + 6 → k = 5
    s = simular(np.array([2]), 4, np.random.default_rng(0), entrada=np.array([2]),
                semanas_alvo=3, execucoes=20)
    assert (s == 5).all()


def test_simular_sorteia_entrega_e_entrada_da_mesma_semana():
    # Semanas históricas: (4 entregues, 4 criados) ou (0, 0). Pareadas, o saldo é sempre 0.
    s = simular(np.array([4, 0]), 1, np.random.default_rng(0), entrada=np.array([4, 0]),
                semanas_alvo=520, execucoes=200, max_semanas=104)
    assert np.isinf(s).all()


def test_simular_e_deterministico_com_mesma_semente():
    r = np.array([0, 1, 3, 2, 0, 5])
    a = simular(r, 20, np.random.default_rng(42))
    b = simular(r, 20, np.random.default_rng(42))
    assert np.array_equal(a, b)


# --- previsão completa ---------------------------------------------------------------

def _abertos(n, id0=500):
    return [it(id0 + i) for i in range(n)]


def test_ritmo_constante_cumpre_com_certeza():
    itens = fechados_por_semana([2] * 12, date(2026, 10, 26)) + _abertos(10)
    p = prever(epic(alvo=HOJE + timedelta(weeks=6)), itens, HOJE, np.random.default_rng(1))
    assert p.secao == "verde"
    assert p.prob_cumprir == 1.0
    assert (p.restante, p.ritmo_medio) == (10, 2.0)
    assert p.p50 == HOJE + timedelta(weeks=5)
    assert p.razao_ritmo == pytest.approx((10 / 6) / 2)


def test_escopo_crescendo_derruba_a_probabilidade():
    # Ritmo de 2/semana e alvo em 6 semanas, mas o escopo ganhou 1 item por semana nas
    # últimas 12: precisa entregar 12 restantes + 6 novos = 18 até o alvo, só dá 12.
    ultima = date(2026, 10, 26)
    novos = [it(700 + k, criado=ultima - timedelta(weeks=k) + timedelta(days=1)) for k in range(12)]
    itens = fechados_por_semana([2] * 12, ultima) + novos
    p = prever(epic(alvo=HOJE + timedelta(weeks=6)), itens, HOJE, np.random.default_rng(1))
    assert (p.restante, p.entrada_media) == (12, 1.0)
    assert p.secao == "vermelho"
    assert p.razao_ritmo == pytest.approx(((12 + 1.0 * 6) / 6) / 2)


def test_ritmo_lento_fica_vermelho():
    itens = fechados_por_semana([1] * 12, date(2026, 10, 26)) + _abertos(30)
    p = prever(epic(alvo=HOJE + timedelta(weeks=4)), itens, HOJE, np.random.default_rng(1))
    assert p.secao == "vermelho"
    assert p.prob_cumprir == 0.0


def test_restante_zero_cumpre():
    itens = fechados_por_semana([1] * 3, date(2026, 10, 26))
    p = prever(epic(alvo=HOJE + timedelta(weeks=2)), itens, HOJE, np.random.default_rng(1))
    assert (p.secao, p.prob_cumprir, p.restante) == ("verde", 1.0, 0)


def test_data_vencida_e_ja_atrasado():
    p = prever(epic(alvo=HOJE - timedelta(days=1)), _abertos(3), HOJE, np.random.default_rng(1))
    assert p.secao == "ja_atrasado"


def test_sem_data_alvo_ou_sem_ritmo_nao_da_para_prever():
    rng = np.random.default_rng(1)
    assert prever(epic(alvo=None), _abertos(3), HOJE, rng).secao == "sem_como_prever"
    assert prever(epic(alvo=None), [], HOJE, rng).secao == "sem_como_prever"
    assert prever(epic(alvo=HOJE + timedelta(weeks=8)), _abertos(3), HOJE, rng).secao == "sem_como_prever"


def test_data_alvo_futura_sem_escopo_e_vermelho_sem_probabilidade():
    # v3: no backtest, 100% dos Epics sem escopo detalhado no corte atrasaram.
    p = prever(epic(alvo=HOJE + timedelta(weeks=8)), [], HOJE, np.random.default_rng(1))
    assert (p.secao, p.prob_cumprir, p.escopo) == ("vermelho", None, 0)


def test_escopo_criado_depois_de_hoje_conta_como_vazio():
    p = prever(epic(alvo=HOJE + timedelta(weeks=8)), [it(1, criado=HOJE + timedelta(days=3))], HOJE,
               np.random.default_rng(1))
    assert p.secao == "vermelho"


def test_itens_criados_ou_fechados_depois_de_hoje_nao_contam():
    # É isto que permite ao backtest chamar prever() com hoje = data de corte.
    corte = date(2026, 8, 3)
    itens = [
        it(1, fechado=date(2026, 7, 29)),                        # concluído antes do corte
        it(2, fechado=date(2026, 8, 20)),                        # fechado depois → aberto no corte
        it(3, criado=date(2026, 9, 1)),                          # não existia no corte
        it(4, criado=date(2026, 9, 1), fechado=date(2026, 9, 9)),
    ]
    p = prever(epic(alvo=date(2026, 10, 1)), itens, corte, np.random.default_rng(1))
    assert (p.escopo, p.concluidos, p.restante) == (2, 1, 1)


@pytest.mark.parametrize("prob,esperado", [
    (0.0, "vermelho"), (0.399, "vermelho"), (0.40, "amarelo"),
    (0.699, "amarelo"), (0.70, "verde"), (1.0, "verde"),
])
def test_fronteiras_do_farol(prob, esperado):
    assert classificar_farol(prob) == esperado


def test_cortes_do_farol_parametrizaveis():
    assert classificar_farol(0.5, cortes=(0.6, 0.8)) == "vermelho"


def test_razao_ritmo_pura_bate_com_a_do_prever():
    from radar.previsao import razao_ritmo
    assert razao_ritmo(10, 2.0, 0.0, 42) == pytest.approx((10 / 6) / 2)
    assert razao_ritmo(12, 2.0, 1.0, 42) == pytest.approx(((12 + 1.0 * 6) / 6) / 2)
    assert razao_ritmo(5, 1.0, 0.0, 3) == pytest.approx(5.0)      # alvo nesta semana: tudo em 1 semana
    assert razao_ritmo(5, 0.0, 0.0, 42) is None
