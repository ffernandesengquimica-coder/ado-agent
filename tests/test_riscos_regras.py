from datetime import date

import pytest

from conftest import item
from radar.dados import carregar
from riscos.regras import CATEGORIAS, avaliar

HOJE = date(2026, 11, 5)
# 12 semanas completas antes da semana de HOJE (segunda 02/11): uma quarta-feira em cada.
SEMANAS = ["2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16",
           "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]


def entregues(epic: int, id0: int, semanas=SEMANAS) -> list[dict]:
    """Um item entregue por semana: ritmo 1/semana, última entrega em 28/10."""
    return [item(id0 + k, "Product Backlog Item", pai=epic, estado="Done", fechado=d) for k, d in enumerate(semanas)]


def restantes(epic: int, id0: int, n: int, **kw) -> list[dict]:
    return [item(id0 + k, "Product Backlog Item", pai=epic, **kw) for k in range(n)]


def sinais(extracao, itens, links=()):
    return avaliar(carregar(extracao(itens, links)), HOJE)


def de(s, epic, categoria):
    return next((x for x in s[epic] if x.categoria == categoria), None)


# --- PRAZO --------------------------------------------------------------------------

@pytest.mark.parametrize("n_restantes, alvo, esperado", [
    (5, "2026-12-31", None),        # 8 semanas, precisa de 0,6/sem: folga
    (10, "2026-12-31", "media"),    # precisa de 1,25/sem: razão 1,25
    (12, "2026-12-31", "alta"),     # precisa de 1,5/sem: razão 1,5 (limiar)
])
def test_prazo_pela_razao_de_ritmo(extracao, n_restantes, alvo, esperado):
    s = sinais(extracao, [item(1, "Epic", alvo=alvo), *entregues(1, 100), *restantes(1, 200, n_restantes)])
    sinal = de(s, 1, "PRAZO")
    assert (sinal.probabilidade if sinal else None) == esperado
    if sinal:
        assert "mais rápido" in sinal.evidencias[0] and sinal.estado == "aberto"


def test_prazo_parado_ha_4_semanas_e_alto_mesmo_com_folga(extracao):
    s = sinais(extracao, [item(1, "Epic", alvo="2027-06-30"), *entregues(1, 100, SEMANAS[:8]),
                          *restantes(1, 200, 2)])
    sinal = de(s, 1, "PRAZO")
    assert sinal.probabilidade == "alta" and sinal.evidencias == ("sem entregas há 5 semanas",)


def test_prazo_com_entrega_ha_menos_de_4_semanas_nao_esta_parado(extracao):
    s = sinais(extracao, [item(1, "Epic", alvo="2027-06-30"), *entregues(1, 100, SEMANAS[:10]),
                          *restantes(1, 200, 2)])
    assert de(s, 1, "PRAZO") is None    # última entrega em 14/10: 22 dias


def test_prazo_sem_nenhuma_entrega_e_alto(extracao):
    s = sinais(extracao, [item(1, "Epic", alvo="2027-06-30"), *restantes(1, 200, 3)])
    assert de(s, 1, "PRAZO").evidencias == ("nenhuma entrega registrada",)


def test_prazo_vencido_e_materializado(extracao):
    s = sinais(extracao, [item(1, "Epic", alvo="2026-09-24"), *restantes(1, 200, 3)])
    sinal = de(s, 1, "PRAZO")
    assert (sinal.estado, sinal.probabilidade) == ("materializado", "alta")
    assert sinal.evidencias == ("data alvo vencida há 6 semanas; 3 itens restantes",)


def test_prazo_nao_dispara_sem_data_sem_escopo_ou_com_tudo_entregue(extracao):
    s = sinais(extracao, [
        item(1, "Epic"), *restantes(1, 200, 3),                       # sem data alvo
        item(2, "Epic", alvo="2026-12-31"),                           # sem escopo
        item(3, "Epic", alvo="2026-12-31"), *entregues(3, 300),       # tudo entregue
    ])
    assert de(s, 1, "PRAZO") is None and de(s, 2, "PRAZO") is None and de(s, 3, "PRAZO") is None


# --- CAPACIDADE ---------------------------------------------------------------------

@pytest.mark.parametrize("sem_dono, esperado", [(1, None), (2, "media"), (4, "media"), (5, "alta")])
def test_capacidade_pela_fracao_sem_responsavel(extracao, sem_dono, esperado):
    s = sinais(extracao, [item(1, "Epic"), *restantes(1, 200, sem_dono, responsavel=""),
                          *restantes(1, 300, 10 - sem_dono)])
    sinal = de(s, 1, "CAPACIDADE")
    assert (sinal.probabilidade if sinal else None) == esperado
    if sinal:
        assert sinal.evidencias == (f"{sem_dono} de 10 itens restantes sem responsável",)


# --- ESCOPO -------------------------------------------------------------------------

def test_escopo_vazio_com_data_futura_e_alto(extracao):
    s = sinais(extracao, [item(1, "Epic", alvo="2026-12-31"), item(2, "Epic"), item(3, "Epic", alvo="2026-10-01")])
    assert de(s, 1, "ESCOPO").evidencias == ("data marcada sem nenhum item detalhado",)
    assert de(s, 2, "ESCOPO") is None and de(s, 3, "ESCOPO") is None


@pytest.mark.parametrize("novos, esperado", [(1, None), (2, "media"), (4, "media"), (5, "alta")])
def test_escopo_cresce_contra_o_escopo_de_4_semanas_atras(extracao, novos, esperado):
    s = sinais(extracao, [item(1, "Epic"), *restantes(1, 200, 10, criado="2026-09-01"),
                          *restantes(1, 300, novos, criado="2026-10-20")])
    sinal = de(s, 1, "ESCOPO")
    assert (sinal.probabilidade if sinal else None) == esperado
    if sinal:
        assert sinal.evidencias == (f"escopo cresceu {novos * 10}% nas últimas 4 semanas (+{novos} itens)",)


def test_epic_novo_sendo_detalhado_nao_conta_como_crescimento(extracao):
    # 4 itens antigos (< 5) e 20 novos: é detalhamento inicial.
    s = sinais(extracao, [item(1, "Epic"), *restantes(1, 200, 4, criado="2026-09-01"),
                          *restantes(1, 300, 20, criado="2026-10-20")])
    assert de(s, 1, "ESCOPO") is None


# --- QUALIDADE ----------------------------------------------------------------------

def test_qualidade_soma_faults_sob_pbis_e_bugs_abertos(extracao):
    s = sinais(extracao, [
        item(1, "Epic"), item(2, "Feature", pai=1),
        *restantes(2, 200, 8),
        item(300, "Bug", pai=2), item(301, "Bug", pai=2),
        item(400, "Fault", pai=200), item(401, "Fault", pai=200), item(402, "Fault", pai=201),
        item(403, "Fault", pai=201, estado="Done", fechado="2026-10-01"),
    ])
    sinal = de(s, 1, "QUALIDADE")
    assert sinal.probabilidade == "alta"       # 3 Faults + 2 Bugs = 5 de 10 restantes
    assert sinal.evidencias == ("3 Faults e 2 Bugs abertos = 50% do restante",)


@pytest.mark.parametrize("faults, restante, esperado", [
    (1, 2, None),        # 50%, mas só 1 problema (< 2)
    (2, 11, None),       # 18%
    (2, 10, "media"),    # 20%
    (5, 11, "media"),    # 45%
    (5, 10, "alta"),     # 50%
])
def test_qualidade_limiares(extracao, faults, restante, esperado):
    s = sinais(extracao, [item(1, "Epic"), *restantes(1, 200, restante),
                          *[item(400 + k, "Fault", pai=200) for k in range(faults)]])
    sinal = de(s, 1, "QUALIDADE")
    assert (sinal.probabilidade if sinal else None) == esperado


# --- GOVERNANCA ---------------------------------------------------------------------

def test_governanca_sem_data_alvo(extracao):
    s = sinais(extracao, [item(1, "Epic"), item(2, "Epic", alvo="2026-12-31")])
    assert de(s, 1, "GOVERNANCA").probabilidade == "media"
    assert de(s, 2, "GOVERNANCA") is None


# --- DEPENDENCIA --------------------------------------------------------------------

def _dois_epics(pred_alvo=None, epic_pred_alvo=None, area_pred="Atlas\\Outro"):
    return [
        item(1, "Epic", alvo=epic_pred_alvo, area=area_pred),
        item(11, "Feature", pai=1, alvo=pred_alvo, area=area_pred),
        item(2, "Epic", alvo="2027-06-30"), item(21, "Feature", pai=2),
    ]


def test_dependencia_de_predecessor_vencido_e_alta_e_entre_programas(extracao):
    s = sinais(extracao, _dois_epics(pred_alvo="2026-10-10"), links=[(11, "Successor", 21)])
    sinal = de(s, 2, "DEPENDENCIA")
    assert sinal.probabilidade == "alta" and sinal.entre_programas
    assert sinal.evidencias == ("depende de #11 (Feature, Outro), vencida em 10/10/2026",)
    assert de(s, 1, "DEPENDENCIA") is None      # o predecessor não depende de ninguém


def test_dependencia_do_mesmo_programa_nao_e_entre_programas(extracao):
    s = sinais(extracao, _dois_epics(pred_alvo="2026-10-10", area_pred="Atlas\\Area"), links=[(11, "Successor", 21)])
    assert not de(s, 2, "DEPENDENCIA").entre_programas


def test_dependencia_de_epic_ja_atrasado_e_alta(extracao):
    s = sinais(extracao, _dois_epics(epic_pred_alvo="2026-10-01"), links=[(11, "Successor", 21)])
    assert de(s, 2, "DEPENDENCIA").evidencias == ("depende de #11 (Feature, Outro), cujo Epic #1 já está atrasado",)


def test_dependencia_de_epic_com_prazo_alto_e_media(extracao):
    itens = _dois_epics(epic_pred_alvo="2027-06-30") + [item(12, "Product Backlog Item", pai=11)]  # sem entregas
    sinal = de(sinais(extracao, itens, links=[(11, "Successor", 21)]), 2, "DEPENDENCIA")
    assert sinal.probabilidade == "media" and not sinal.entre_programas


def test_dependencia_de_predecessor_em_dia_nao_e_risco(extracao):
    s = sinais(extracao, _dois_epics(pred_alvo="2027-01-10"), links=[(11, "Successor", 21)])
    assert de(s, 2, "DEPENDENCIA") is None


def test_dependencia_resume_evidencias_alem_de_3(extracao):
    itens = [item(1, "Epic", area="Atlas\\Outro"), *[item(10 + k, "Feature", pai=1, alvo="2026-10-10") for k in range(5)],
             item(2, "Epic"), item(21, "Feature", pai=2)]
    sinal = de(sinais(extracao, itens, links=[(10 + k, "Successor", 21) for k in range(5)]), 2, "DEPENDENCIA")
    assert len(sinal.evidencias) == 4 and sinal.evidencias[-1] == "e mais 2 dependências"


# --- Conjunto -----------------------------------------------------------------------

def test_um_sinal_por_categoria_na_ordem_e_so_epics_abertos(extracao):
    s = sinais(extracao, [
        item(1, "Epic"), *restantes(1, 200, 3, responsavel=""),
        item(2, "Epic", estado="Done", fechado="2026-10-01"),
        item(3, "Epic", estado="Removed"),
    ])
    assert sorted(s) == [1]
    categorias = [x.categoria for x in s[1]]
    assert categorias == sorted(categorias, key=CATEGORIAS.index)
    assert categorias == ["CAPACIDADE", "GOVERNANCA"]       # sem data alvo: não há PRAZO


def test_avaliar_e_deterministico(extracao):
    pasta = extracao([item(1, "Epic", alvo="2026-12-31"), *entregues(1, 100), *restantes(1, 200, 12)])
    d = carregar(pasta)
    assert avaliar(d, HOJE) == avaliar(d, HOJE)


@pytest.mark.parametrize("alvo, texto", [("2026-11-04", "há 1 dia"), ("2026-10-30", "há 6 dias"),
                                         ("2026-10-29", "há 1 semana")])
def test_prazo_vencido_ha_menos_de_uma_semana_fala_em_dias(extracao, alvo, texto):
    s = sinais(extracao, [item(1, "Epic", alvo=alvo), *restantes(1, 200, 1)])
    assert de(s, 1, "PRAZO").evidencias == (f"data alvo vencida {texto}; 1 item restante",)


def test_dependencia_conta_cada_predecessor_uma_vez(extracao):
    # Duas Features do Epic 2 dependem da mesma Feature vencida do Epic 1.
    itens = [item(1, "Epic", area="Atlas\\Outro"),
             item(11, "Feature", pai=1, alvo="2026-10-10", area="Atlas\\Outro"),
             item(2, "Epic"), item(21, "Feature", pai=2), item(22, "Feature", pai=2)]
    sinal = de(sinais(extracao, itens, links=[(11, "Successor", 21), (11, "Successor", 22)]), 2, "DEPENDENCIA")
    assert sinal.evidencias == ("depende de #11 (Feature, Outro), vencida em 10/10/2026",)


# --- Exibição de valores extremos (só a frase muda) ----------------------------------

@pytest.mark.parametrize("n_restantes, texto", [(80, "precisa entregar 10,0× mais rápido"),
                                                (81, "precisa entregar mais de 10× mais rápido")])
def test_razao_acima_de_10_vira_mais_de_10(extracao, n_restantes, texto):
    s = sinais(extracao, [item(1, "Epic", alvo="2026-12-31"), *entregues(1, 100), *restantes(1, 200, n_restantes)])
    sinal = de(s, 1, "PRAZO")
    assert sinal.evidencias[0] == texto and sinal.probabilidade == "alta"


@pytest.mark.parametrize("novos, texto", [(30, "escopo cresceu 300% nas últimas 4 semanas (+30 itens)"),
                                          (31, "escopo mais que quadruplicou nas últimas 4 semanas (+31 itens)")])
def test_crescimento_acima_de_300_porcento_vira_quadruplicou(extracao, novos, texto):
    s = sinais(extracao, [item(1, "Epic"), *restantes(1, 200, 10, criado="2026-09-01"),
                          *restantes(1, 300, novos, criado="2026-10-20")])
    assert de(s, 1, "ESCOPO").evidencias == (texto,)
