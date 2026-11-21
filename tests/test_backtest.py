from datetime import date

import pytest

from conftest import item
from radar.backtest import Metricas, atrasou, avaliaveis, executar, ingenuo_preve_atraso, metricas, passou_portao
from radar.dados import Item, carregar

CORTE = date(2026, 8, 3)
HOJE = date(2026, 11, 5)


def ep(*, criado=date(2026, 3, 2), fechado=None, estado=None, inicio=None, alvo=date(2026, 10, 1), id=1):
    estado = estado or ("Done" if fechado else "New")
    return Item(id=id, tipo="Epic", titulo="E", estado=estado, area="A", responsavel="P",
                criado=criado, fechado=fechado, inicio=inicio, alvo=alvo)


# --- verdade -------------------------------------------------------------------

def pbi(id, *, criado=date(2026, 3, 2), fechado=None):
    return Item(id=id, tipo="Product Backlog Item", titulo="P", estado="Done" if fechado else "New",
                area="A", responsavel="P", criado=criado, fechado=fechado, inicio=None, alvo=None)


def test_cumpriu_se_todo_o_escopo_foi_entregue_ate_a_data_alvo():
    e = ep(alvo=date(2026, 10, 1))
    assert not atrasou(e, [pbi(1, fechado=date(2026, 9, 1)), pbi(2, fechado=date(2026, 10, 1))])
    assert atrasou(e, [pbi(1, fechado=date(2026, 9, 1)), pbi(2, fechado=date(2026, 10, 2))])
    assert atrasou(e, [pbi(1, fechado=date(2026, 9, 1)), pbi(2)])


def test_epic_fechado_tarde_com_escopo_entregue_a_tempo_cumpriu():
    # O caso que reprovou a v1: o trabalho terminou, alguém só fechou o Epic depois.
    e = ep(alvo=date(2026, 10, 1), fechado=date(2026, 11, 2))
    assert not atrasou(e, [pbi(1, fechado=date(2026, 9, 20))])


def test_itens_criados_depois_da_data_alvo_nao_contam():
    e = ep(alvo=date(2026, 10, 1))
    assert not atrasou(e, [pbi(1, fechado=date(2026, 9, 1)), pbi(2, criado=date(2026, 10, 5))])


def test_sem_escopo_na_data_alvo_nao_ha_verdade():
    e = ep(alvo=date(2026, 10, 1))
    assert atrasou(e, []) is None
    assert atrasou(e, [pbi(1, criado=date(2026, 10, 5))]) is None


# --- quem entra no backtest ------------------------------------------------------

@pytest.mark.parametrize("epic,entra", [
    (ep(), True),
    (ep(criado=date(2026, 8, 10)), False),                    # não existia no corte
    (ep(fechado=date(2026, 7, 20)), False),                   # já fechado no corte
    (ep(alvo=date(2026, 7, 31)), False),                      # alvo antes do corte
    (ep(alvo=date(2026, 11, 20)), False),                     # alvo ainda não chegou: sem verdade
    (ep(alvo=None), False),
    (ep(estado="Removed"), False),                            # removido não cumpre nem atrasa
    (ep(fechado=date(2026, 9, 15)), True),                    # aberto no corte, fechado depois
])
def test_avaliaveis(epic, entra):
    assert (avaliaveis({1: epic}, CORTE, HOJE) == [epic]) is entra


# --- baselines -------------------------------------------------------------------

def test_ingenuo_compara_progresso_com_tempo_decorrido():
    e = ep(inicio=date(2026, 6, 1), alvo=date(2026, 10, 1))  # corte em ~51% do tempo
    assert ingenuo_preve_atraso(e, concluidos=3, escopo=10, corte=CORTE)
    assert not ingenuo_preve_atraso(e, concluidos=6, escopo=10, corte=CORTE)


def test_ingenuo_sem_data_inicio_usa_criacao():
    e = ep(criado=date(2026, 6, 1), inicio=None, alvo=date(2026, 10, 1))
    assert ingenuo_preve_atraso(e, concluidos=3, escopo=10, corte=CORTE)


# --- métricas ---------------------------------------------------------------------

def test_metricas_calculadas_a_mao():
    m = metricas(previsto=[True, True, False, False], real=[True, False, True, False])
    assert (m.vp, m.fp, m.fn, m.n) == (1, 1, 1, 4)
    assert (m.precisao, m.recall, m.f1, m.taxa_base) == (0.5, 0.5, 0.5, 0.5)


def test_metricas_sem_previsao_positiva_nao_divide_por_zero():
    m = metricas(previsto=[False, False], real=[True, False])
    assert (m.precisao, m.recall, m.f1) == (0.0, 0.0, 0.0)


def _m(p, r, f1, taxa):
    return Metricas(n=100, vp=0, fp=0, fn=0, precisao=p, recall=r, f1=f1, taxa_base=taxa)


def test_portao_exige_recall_precisao_acima_da_base_e_bater_os_dois_baselines():
    ing, triv = _m(0.7, 0.5, 0.58, 0.63), _m(0.63, 1.0, 0.77, 0.63)
    assert passou_portao(_m(0.75, 0.80, 0.78, 0.63), ing, triv)
    assert not passou_portao(_m(0.75, 0.65, 0.78, 0.63), ing, triv)   # recall < 70%
    assert not passou_portao(_m(0.70, 0.90, 0.79, 0.63), ing, triv)   # precisão < base + 10 p.p.
    assert not passou_portao(_m(0.74, 0.80, 0.76, 0.63), ing, triv)   # F1 não bate o trivial


# --- ponta a ponta ------------------------------------------------------------------

def test_executar_monta_linhas_por_corte_e_agregado(extracao):
    itens = [
        # Epic 1: ritmo de 1/semana, 20 restantes, alvo em 4 semanas → vermelho; atrasou (aberto)
        item(1, "Epic", criado="2026-03-02", alvo="2026-08-31"),
        *[item(100 + k, "Product Backlog Item", pai=1, estado="Done", fechado=f"2026-{m:02d}-{d:02d}")
          for k, (m, d) in enumerate([(5, 13), (5, 20), (5, 27), (6, 3), (6, 10), (6, 17),
                                      (6, 24), (7, 1), (7, 8), (7, 15), (7, 22), (7, 29)])],
        *[item(200 + k, "Product Backlog Item", pai=1) for k in range(20)],
        # Epic 2: tudo concluído, fechado antes do alvo → verde; cumpriu
        item(2, "Epic", criado="2026-03-02", alvo="2026-09-30", estado="Done", fechado="2026-09-01"),
        item(300, "Product Backlog Item", pai=2, estado="Done", fechado="2026-07-01"),
    ]
    resultado = executar(carregar(extracao(itens)), [CORTE], HOJE, semente=42)
    por = {(l["corte"], l["preditor"]): l for l in resultado.linhas}
    assert set(por) == {(c, p) for c in ["2026-08-03", "agregado"] for p in ["modelo", "ingenuo", "trivial"]}
    modelo = por[("2026-08-03", "modelo")]
    assert (modelo["n"], modelo["vp"], modelo["fp"], modelo["fn"]) == (2, 1, 0, 0)
    assert por[("2026-08-03", "trivial")]["fp"] == 1
    assert [d["epic_id"] for d in resultado.detalhe] == [1, 2]
