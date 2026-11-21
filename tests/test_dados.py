from datetime import date

import pytest

from conftest import item
from radar.dados import carregar, ultima_extracao


def test_escopo_vai_para_o_epic_mais_proximo(extracao):
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Epic", pai=1),
        item(3, "Feature", pai=2),
        item(4, "Product Backlog Item", pai=3),
        item(5, "Bug", pai=1),
    ]))
    assert [i.id for i in d.escopo[2]] == [4]
    assert [i.id for i in d.escopo[1]] == [5]


def test_escopo_so_tipos_de_trabalho_entregavel(extracao):
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Feature", pai=1),
        item(3, "Product Backlog Item", pai=2),
        item(4, "Habilitator", pai=2),
        item(5, "Spike", pai=2),
        item(6, "Task", pai=3),
        item(7, "Test Case", pai=2),
    ]))
    assert sorted(i.id for i in d.escopo[1]) == [3, 4, 5]


def test_removed_fica_fora_do_escopo(extracao):
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Product Backlog Item", pai=1, estado="Removed"),
        item(3, "Product Backlog Item", pai=1, estado="Done", fechado="2026-04-01"),
    ]))
    assert [i.id for i in d.escopo[1]] == [3]


def test_item_sem_epic_acima_e_ignorado(extracao):
    d = carregar(extracao([
        item(1, "Feature"),
        item(2, "Product Backlog Item", pai=1),
        item(3, "Epic"),
    ]))
    assert d.escopo.get(3, []) == []
    assert all(i.id != 2 for itens in d.escopo.values() for i in itens)


def test_features_vao_para_o_epic_mais_proximo(extracao):
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Feature", pai=1, alvo="2026-10-01"),
        item(3, "Epic", pai=1),
        item(4, "Feature", pai=3),
        item(5, "Feature"),
    ]))
    assert [f.id for f in d.features[1]] == [2]
    assert [f.id for f in d.features[3]] == [4]
    assert d.features[1][0].alvo == date(2026, 10, 1)


def test_todos_os_epics_sao_carregados_inclusive_fechados(extracao):
    # O backtest precisa de Epics que estavam abertos no passado e hoje estão Done.
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Epic", estado="Done", fechado="2026-09-01"),
        item(3, "Epic", estado="Removed"),
    ]))
    assert sorted(d.epics) == [1, 2, 3]


def test_datas_tipadas_e_vazias_viram_none(extracao):
    d = carregar(extracao([
        item(1, "Epic", criado="2026-03-02", inicio="2026-03-09", alvo="2026-12-15"),
        item(2, "Product Backlog Item", pai=1, estado="Done", fechado="2026-04-01"),
    ]))
    e, pbi = d.epics[1], d.escopo[1][0]
    assert (e.criado, e.inicio, e.alvo, e.fechado) == (date(2026, 3, 2), date(2026, 3, 9), date(2026, 12, 15), None)
    assert pbi.fechado == date(2026, 4, 1)


def test_ultima_extracao_pega_a_pasta_mais_recente(tmp_path):
    base = tmp_path / "out" / "Atlas"
    for nome in ["20261001T000000Z", "20261105T003131Z", "20261020T000000Z"]:
        (base / nome).mkdir(parents=True)
    (base / "latest.txt").write_text("x")
    assert ultima_extracao(tmp_path / "out", "Atlas").name == "20261105T003131Z"


def test_ultima_extracao_sem_pastas_falha(tmp_path):
    with pytest.raises(FileNotFoundError):
        ultima_extracao(tmp_path / "out", "Atlas")


# --- Agente de Riscos: Epic de cada item, Faults e dependências -------------------------

def test_epic_de_aponta_o_epic_mais_proximo_e_o_proprio_epic(extracao):
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Epic", pai=1),
        item(3, "Feature", pai=2),
        item(4, "Product Backlog Item", pai=3),
        item(5, "Feature"),
    ]))
    assert d.epic_de[1] == 1 and d.epic_de[2] == 2
    assert d.epic_de[3] == 2 and d.epic_de[4] == 2
    assert 5 not in d.epic_de


def test_faults_sob_pbi_vao_para_o_epic_e_removed_fica_fora(extracao):
    d = carregar(extracao([
        item(1, "Epic"),
        item(2, "Feature", pai=1),
        item(3, "Product Backlog Item", pai=2),
        item(4, "Fault", pai=3),
        item(5, "Fault", pai=3, estado="Removed"),
        item(6, "Fault"),
    ]))
    assert [f.id for f in d.faults[1]] == [4]
    assert all(f.id not in (4, 5) for f in d.escopo[1])   # Fault não é escopo do Radar


def test_dependencia_usa_a_direcao_do_link_successor(extracao):
    # O link Successor gravado em 11 aponta para 21: 21 (Epic 2) depende de 11 (Epic 1).
    d = carregar(extracao([
        item(1, "Epic"), item(11, "Feature", pai=1),
        item(2, "Epic"), item(21, "Feature", pai=2),
    ], links=[(11, "Successor", 21), (21, "Predecessor", 11)]))
    assert [(p.id, s.id) for p, s in d.dependencias] == [(11, 21)]


def test_dependencia_ignora_mesmo_epic_itens_fechados_e_sucessor_sem_epic(extracao):
    d = carregar(extracao([
        item(1, "Epic"), item(11, "Feature", pai=1), item(12, "Feature", pai=1),
        item(13, "Feature", pai=1, estado="Done", fechado="2026-09-01"),
        item(2, "Epic"), item(21, "Feature", pai=2),
        item(3, "Feature"),                                   # sem Epic acima
        item(4, "Feature"),                                   # predecessor sem Epic: vale
    ], links=[(11, "Successor", 12),                          # mesmo Epic
              (13, "Successor", 21),                          # predecessor fechado
              (11, "Successor", 3),                           # sucessor sem Epic
              (4, "Successor", 21),
              (11, "Related", 21)]))                          # outro tipo de link
    assert [(p.id, s.id) for p, s in d.dependencias] == [(4, 21)]


def test_sem_arquivo_de_links_nao_ha_dependencias(extracao):
    pasta = extracao([item(1, "Epic")])
    (pasta / "workitem_links.csv").unlink()
    assert carregar(pasta).dependencias == []
