from collections import Counter
from datetime import date

from conftest import item
from radar.dados import carregar
from radar.narrativa import NarradorNulo
from radar.relatorio import ORDEM_SECOES, gerar_html, linhas_relatorio

HOJE = date(2026, 11, 5)


def _cenario():
    semanas = ["2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16",
               "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]
    entregues = lambda epic, id0: [item(id0 + k, "Product Backlog Item", pai=epic, estado="Done", fechado=d)
                                   for k, d in enumerate(semanas)]
    return [
        # 1: 1/semana, 30 restantes, alvo em ~4 semanas → vermelho
        item(1, "Epic", alvo="2026-12-03"), *entregues(1, 100),
        *[item(200 + k, "Product Backlog Item", pai=1, responsavel="") for k in range(30)],
        # 2: 1/semana, 2 restantes, alvo em ~8 semanas → verde
        item(2, "Epic", alvo="2026-12-31"), *entregues(2, 300),
        *[item(400 + k, "Product Backlog Item", pai=2) for k in range(2)],
        # 3: data vencida
        item(3, "Epic", alvo="2026-10-01"), item(500, "Product Backlog Item", pai=3),
        # 4: sem data alvo
        item(4, "Epic"),
        # 5: sem escopo → vermelho
        item(5, "Epic", alvo="2027-01-15"),
        # 6 e 7: fechados ou removidos não entram
        item(6, "Epic", estado="Done", fechado="2026-09-01", alvo="2026-09-30"),
        item(7, "Epic", estado="Removed", alvo="2026-12-01"),
    ]


def test_todo_epic_aberto_aparece_uma_vez_com_a_secao_certa(extracao):
    linhas = linhas_relatorio(carregar(extracao(_cenario())), HOJE, semente=42)
    secao = {l["epic_id"]: l["secao"] for l in linhas}
    assert Counter(l["epic_id"] for l in linhas) == Counter({1: 1, 2: 1, 3: 1, 4: 1, 5: 1})
    assert secao == {1: "vermelho", 2: "verde", 3: "ja_atrasado", 4: "sem_como_prever", 5: "vermelho"}


def test_linhas_ordenadas_por_secao_e_motivos_preenchidos(extracao):
    linhas = linhas_relatorio(carregar(extracao(_cenario())), HOJE, semente=42)
    ordem = [ORDEM_SECOES.index(l["secao"]) for l in linhas]
    assert ordem == sorted(ordem)
    l1 = next(l for l in linhas if l["epic_id"] == 1)
    assert "itens restantes sem responsável" in l1["motivos"]
    assert next(l for l in linhas if l["epic_id"] == 5)["motivos"] == "data marcada sem nenhum item detalhado"
    assert all(l["modelo_versao"] == "v3" and l["data_previsao"] == "2026-11-05" for l in linhas)


def test_mesma_entrada_e_semente_dao_o_mesmo_resultado(extracao):
    d = carregar(extracao(_cenario()))
    assert linhas_relatorio(d, HOJE, semente=7) == linhas_relatorio(d, HOJE, semente=7)


# --- HTML -----------------------------------------------------------------------

def _html(extracao, narrador=None):
    linhas = linhas_relatorio(carregar(extracao(_cenario())), HOJE, semente=42)
    kwargs = {"narrador": narrador} if narrador else {}
    return gerar_html(linhas, HOJE, "20261105T003131Z", **kwargs), linhas


def test_html_tem_aviso_de_uso_interno_e_reconciliacao(extracao):
    html, _ = _html(extracao)
    assert "Uso interno" in html and "v3" in html
    assert "5 Epics abertos" in html
    for titulo in ["Vão atrasar", "Atenção", "Já atrasados", "Sem como prever", "No prazo"]:
        assert titulo in html


def test_html_mostra_os_campos_de_cada_epic(extracao):
    html, linhas = _html(extracao)
    assert all(f">{l['epic_id']}<" in html for l in linhas)
    assert "03/12/2026" in html                       # data alvo do Epic 1 em formato brasileiro
    assert "data marcada sem nenhum item detalhado" in html


def test_html_e_autocontido_e_escapa_textos(extracao):
    itens = _cenario()
    itens[0] = {**itens[0], "titulo": "<script>alert(1)</script> & cia"}
    linhas = linhas_relatorio(carregar(extracao(itens)), HOJE, semente=42)
    html = gerar_html(linhas, HOJE, "x")
    assert "<script>alert(1)" not in html                 # título nunca entra cru
    assert html.lower().count("<script") == 1             # só o script embutido do painel
    assert "<script src" not in html.lower() and "<link" not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; cia" in html
    assert "http://" not in html and "https://" not in html


def test_html_tem_legenda_das_colunas(extracao):
    html, _ = _html(extracao)
    assert "Como ler este relatório" in html
    for coluna in ["Chance", "P50", "P85", "Restante", "Ritmo/sem", "Razão"]:
        assert f"<dt>{coluna}</dt>" in html
    assert "a data segura para prometer" in html


def test_html_tem_filtros_por_secao_programa_e_prazo(extracao):
    html, linhas = _html(extracao)
    assert html.count("data-busca=") == len(linhas)         # uma linha de tabela por Epic
    for s in ORDEM_SECOES:
        assert f'data-filtro="secao" data-valor="{s}"' in html
    assert 'data-filtro="programa"' in html and 'data-filtro="mes" data-valor="vencida"' in html
    assert 'data-secao="ja_atrasado"' in html and 'data-mes="vencida"' in html
    assert 'class="f-busca"' in html and 'role="tab"' not in html   # sem riscos, sem abas


def test_narrador_nulo_nao_acrescenta_nada_e_narrador_recebe_a_linha(extracao):
    assert NarradorNulo().narrar({"epic_id": 1}) == ""

    class Eco:
        def narrar(self, linha):
            return f"narrativa do epic {linha['epic_id']}"

    html, _ = _html(extracao, narrador=Eco())
    assert "narrativa do epic 1" in html
