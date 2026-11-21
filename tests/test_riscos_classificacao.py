from datetime import date

import pytest

from conftest import item
from radar.dados import Item, carregar
from riscos.classificacao import criticidade, dependentes, gatilhos, impacto
from riscos.regras import Sinal

HOJE = date(2026, 11, 5)


def epic(alvo: date | None = None, responsavel: str = "Pessoa") -> Item:
    return Item(id=1, tipo="Epic", titulo="Epic 1", estado="New", area="Atlas\\Area", responsavel=responsavel,
                criado=date(2026, 3, 2), fechado=None, inicio=None, alvo=alvo)


PRAZO_ALTA = Sinal("PRAZO", "alta", ("x",))


@pytest.mark.parametrize("restante, deps, vazio, esperado", [
    (30, 0, False, "alto"), (29, 0, False, "medio"), (5, 2, False, "alto"),
    (10, 0, False, "medio"), (9, 0, False, "baixo"), (0, 1, False, "medio"),
    (0, 0, True, "medio"), (0, 0, False, "baixo"),
])
def test_impacto(restante, deps, vazio, esperado):
    assert impacto(restante, deps, vazio) == esperado


@pytest.mark.parametrize("prob, imp, esperado", [
    ("alta", "alto", "critico"), ("alta", "medio", "alto"), ("alta", "baixo", "medio"),
    ("media", "alto", "alto"), ("media", "medio", "medio"), ("media", "baixo", "baixo"),
])
def test_matriz_de_criticidade(prob, imp, esperado):
    assert criticidade(prob, imp) == esperado


@pytest.mark.parametrize("dias, crit, escala", [
    (0, "critico", True), (27, "critico", True), (28, "critico", True), (29, "critico", False),
    (10, "alto", False), (-1, "critico", False),
])
def test_gatilho_data_proxima(dias, crit, escala):
    from datetime import timedelta
    g = gatilhos(PRAZO_ALTA, epic(alvo=HOJE + timedelta(days=dias)), crit, HOJE)
    assert ("data_proxima" in g) is escala


def test_gatilho_dependencia_so_alta_e_entre_programas():
    e = epic(alvo=date(2027, 6, 30))
    assert gatilhos(Sinal("DEPENDENCIA", "alta", ("x",), entre_programas=True), e, "alto", HOJE) == (
        "dependencia_entre_programas",)
    assert gatilhos(Sinal("DEPENDENCIA", "alta", ("x",), entre_programas=False), e, "alto", HOJE) == ()
    assert gatilhos(Sinal("DEPENDENCIA", "media", ("x",), entre_programas=True), e, "alto", HOJE) == ()


@pytest.mark.parametrize("alvo, escala", [(date(2026, 9, 10), False), (date(2026, 9, 9), True)])  # hoje − 8 sem = 10/09
def test_gatilho_atraso_grande_passa_de_8_semanas(alvo, escala):
    s = Sinal("PRAZO", "alta", ("x",), estado="materializado")
    assert ("atraso_grande" in gatilhos(s, epic(alvo=alvo), "medio", HOJE)) is escala


def test_gatilho_sem_dono_so_quando_critico():
    e = epic(alvo=date(2027, 6, 30), responsavel="")
    assert gatilhos(PRAZO_ALTA, e, "critico", HOJE) == ("sem_dono",)
    assert gatilhos(PRAZO_ALTA, e, "alto", HOJE) == ()
    assert gatilhos(PRAZO_ALTA, epic(alvo=date(2027, 6, 30)), "critico", HOJE) == ()


def test_varios_gatilhos_na_ordem():
    e = epic(alvo=HOJE, responsavel="")
    assert gatilhos(PRAZO_ALTA, e, "critico", HOJE) == ("data_proxima", "sem_dono")


def test_dependentes_conta_epics_distintos(extracao):
    d = carregar(extracao([
        item(1, "Epic"), item(11, "Feature", pai=1), item(12, "Feature", pai=1),
        item(2, "Epic"), item(21, "Feature", pai=2), item(22, "Feature", pai=2),
        item(3, "Epic"), item(31, "Feature", pai=3),
    ], links=[(11, "Successor", 21), (12, "Successor", 22), (11, "Successor", 31)]))
    assert dependentes(d) == {1: 2}
