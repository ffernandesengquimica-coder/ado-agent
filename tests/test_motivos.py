from datetime import date, timedelta

import pytest

from radar.dados import Item
from radar.motivos import motivos
from radar.previsao import Previsao

HOJE = date(2026, 11, 5)


def it(id, *, criado=date(2026, 3, 2), fechado=None, responsavel="P", tipo="Product Backlog Item",
       estado=None, alvo=None):
    estado = estado or ("Done" if fechado else "New")
    return Item(id=id, tipo=tipo, titulo=f"{tipo} {id}", estado=estado, area="A", responsavel=responsavel,
                criado=criado, fechado=fechado, inicio=None, alvo=alvo)


def prev(secao="vermelho", razao=1.0, escopo=10):
    return Previsao(epic_id=1, secao=secao, escopo=escopo, concluidos=0, restante=escopo, ritmo_medio=1.0,
                    entrada_media=0.0, prob_cumprir=0.2, p50=None, p85=None, razao_ritmo=razao)


def entregue_ha(dias, id=900):
    return it(id, fechado=HOJE - timedelta(days=dias))


def test_so_vermelho_e_amarelo_tem_motivos():
    itens = [it(1, responsavel="")]  # dispararia "sem responsável"
    assert motivos(prev("verde", razao=3.0), itens, [], HOJE) == []
    assert motivos(prev("sem_como_prever", razao=3.0), itens, [], HOJE) == []
    assert motivos(prev("amarelo", razao=3.0), itens + [entregue_ha(3)], [], HOJE)


@pytest.mark.parametrize("razao,dispara", [(1.49, False), (1.5, True), (2.13, True), (None, False)])
def test_precisa_acelerar(razao, dispara):
    m = motivos(prev(razao=razao), [entregue_ha(3)], [], HOJE)
    assert any("mais rápido" in x for x in m) is dispara
    if razao == 2.13:
        assert "precisa entregar 2,1× mais rápido" in m


@pytest.mark.parametrize("dias,dispara", [(27, False), (28, True), (60, True)])
def test_parado_sem_entregas_ha_4_semanas(dias, dispara):
    m = motivos(prev(), [entregue_ha(dias), it(2)], [], HOJE)
    assert any("sem entregas" in x for x in m) is dispara


def test_parado_sem_nenhuma_entrega():
    assert "nenhuma entrega registrada" in motivos(prev(), [it(1)], [], HOJE)


def test_escopo_crescendo_contra_o_escopo_de_4_semanas_atras():
    antigos = [it(i) for i in range(1, 9)] + [entregue_ha(3)]                      # 9 itens há 4 semanas
    recente = HOJE - timedelta(days=10)
    m11 = motivos(prev(), antigos + [it(50, criado=recente)], [], HOJE)               # 1 ÷ 9 = 11%
    m22 = motivos(prev(), antigos + [it(50, criado=recente), it(51, criado=recente)], [], HOJE)  # 2 ÷ 9 = 22%
    m33 = motivos(prev(), antigos + [it(50 + k, criado=recente) for k in range(3)], [], HOJE)   # 3 ÷ 9 = 33%
    assert not any("escopo" in x for x in m11)
    assert "escopo cresceu 22% nas últimas 4 semanas (+2 itens)" in m22
    assert "escopo cresceu 33% nas últimas 4 semanas (+3 itens)" in m33


def test_escopo_com_menos_de_5_itens_ha_4_semanas_esta_sendo_detalhado():
    recente = HOJE - timedelta(days=10)
    m = motivos(prev(), [it(1), it(2), it(3), entregue_ha(3)] + [it(50 + k, criado=recente) for k in range(6)], [], HOJE)
    assert not any("escopo" in x for x in m)


def test_escopo_mais_que_quadruplicou_igual_aos_riscos():
    recente = HOJE - timedelta(days=10)
    base = [it(i) for i in range(1, 5)] + [entregue_ha(3)]                          # 5 itens há 4 semanas
    m = motivos(prev(), base + [it(50 + k, criado=recente) for k in range(16)], [], HOJE)   # 16 ÷ 5 = 320%
    assert "escopo mais que quadruplicou nas últimas 4 semanas (+16 itens)" in m


def test_sem_responsavel_a_partir_de_20_porcento_do_restante():
    base = [entregue_ha(3)] + [it(i) for i in range(1, 5)]                       # 4 restantes com dono
    assert not any("responsável" in x for x in motivos(prev(), base, [], HOJE))
    m = motivos(prev(), base + [it(10, responsavel="")], [], HOJE)                # 1 de 5 = 20%
    assert "1 de 5 itens restantes sem responsável" in m


def test_features_vencidas():
    feats = [it(70, tipo="Feature", alvo=HOJE - timedelta(days=5)),
             it(71, tipo="Feature", alvo=HOJE - timedelta(days=1)),
             it(72, tipo="Feature", alvo=HOJE - timedelta(days=1), estado="Done", fechado=HOJE - timedelta(days=2)),
             it(73, tipo="Feature", alvo=HOJE + timedelta(days=9))]
    assert "2 Features com data alvo vencida" in motivos(prev(), [entregue_ha(3)], feats, HOJE)
    assert not any("Feature" in x for x in motivos(prev(), [entregue_ha(3)], feats[2:], HOJE))


def test_feature_sem_data_alvo_nao_conta_como_vencida():
    feats = [it(70, tipo="Feature", alvo=None), it(71, tipo="Feature", alvo=HOJE - timedelta(days=1))]
    assert "1 Feature com data alvo vencida" in motivos(prev(), [entregue_ha(3)], feats, HOJE)


def test_sem_escopo_detalhado():
    assert motivos(prev(escopo=0, razao=None), [], [], HOJE) == ["data marcada sem nenhum item detalhado"]
