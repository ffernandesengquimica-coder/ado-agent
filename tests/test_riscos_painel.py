from datetime import date

from conftest import item
from radar.dados import carregar
from radar.relatorio import gerar_html, linhas_relatorio
from riscos.painel import gerar_aba
from riscos.registro import linhas_csv, montar, saidas

HOJE = date(2026, 11, 5)


def _cenario():
    return [
        item(1, "Epic", alvo="2026-09-01", responsavel=""),                       # materializado; escala
        *[item(100 + k, "Product Backlog Item", pai=1, responsavel="") for k in range(31)],
        item(2, "Epic"), *[item(200 + k, "Product Backlog Item", pai=2, responsavel="") for k in range(3)],
        item(3, "Epic", alvo="2026-12-31"),                                       # sem escopo
    ]


def _aba(extracao, itens=None, anteriores=(), anterior=None):
    d = carregar(extracao(itens or _cenario()))
    riscos = montar(d, HOJE)
    linhas = linhas_csv(riscos, d, HOJE, list(anteriores))
    return gerar_aba(linhas, saidas(riscos, list(anteriores), d), anterior), linhas, d


def test_uma_linha_por_risco_e_reconciliacao(extracao):
    html, linhas, _ = _aba(extracao)
    assert html.count("data-risco=") == len(linhas) == 5
    for l in linhas:
        assert f'data-risco="{l["risco_id"]}"' in html
    # Epic 3 sem escopo: impacto médio por regra (tamanho desconhecido) → ESCOPO alta × médio = alto.
    assert "5 riscos = 2 crítico + 1 alto + 1 médio + 1 baixo · 3 Epics com pelo menos um risco" in html


def test_aviso_so_enquanto_nao_aprovado_e_legenda(extracao, monkeypatch):
    import riscos.painel as painel
    monkeypatch.setattr(painel, "RISCOS_APROVADOS", False)
    html, _, _ = _aba(extracao)
    assert "Uso interno — regras em revisão" in html
    monkeypatch.setattr(painel, "RISCOS_APROVADOS", True)
    html, _, _ = _aba(extracao)
    assert "Uso interno" not in html
    assert "Como ler o registro de riscos" in html and "<dt>Dependência</dt>" in html


def test_bloco_escalar_agrupa_por_epic(extracao):
    html, linhas, _ = _aba(extracao)
    escalados = {l["epic_id"] for l in linhas if l["escalar"] == "sim"}
    assert escalados == {1}
    assert "Escalar para a diretoria (1 Epics)" in html
    assert 'data-filtro="epic" data-valor="1"' in html
    assert "atrasado há mais de 8 semanas" in html and "Epic sem dono" in html


def test_filtros_cartoes_matriz_e_categorias(extracao):
    html, _, _ = _aba(extracao)
    for trecho in ['data-filtro="escalar" data-valor="sim"', 'data-filtro="criticidade" data-valor="critico"',
                   'data-filtro="estado" data-valor="materializado"', 'data-filtro="celula" data-valor="alta-alto"',
                   'data-filtro="categoria" data-valor="PRAZO"', 'data-filtro-sel="categoria"',
                   'data-filtro-sel="programa"', 'class="f-busca"']:
        assert trecho in html
    assert 'data-celula="alta-alto"' in html and 'data-estado="materializado"' in html


def test_escapa_textos(extracao):
    itens = _cenario()
    itens[0] = {**itens[0], "titulo": '<img src=x onerror="alert(1)"> & cia'}
    html, _, _ = _aba(extracao, itens)
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; cia" in html


def test_saidas_so_com_registro_anterior(extracao):
    html, _, _ = _aba(extracao)
    assert "Saíram do registro" not in html and "Nenhum risco saiu" not in html

    html, _, _ = _aba(extracao, anterior=date(2026, 10, 29))
    assert "Nenhum risco saiu do registro desde 29/10/2026." in html

    ant = [{"risco_id": "R-2-ESCOPO", "epic_id": "2", "titulo": "Epic 2", "categoria": "ESCOPO",
            "criticidade": "medio", "estado": "aberto"}]
    html, _, _ = _aba(extracao, anteriores=ant, anterior=date(2026, 10, 29))
    assert "Saíram do registro desde 29/10/2026 (1)" in html and "sinal desapareceu" in html


def test_movimento_aparece_com_a_criticidade_anterior(extracao):
    ant = [{"risco_id": "R-2-GOVERNANCA", "epic_id": "2", "criticidade": "medio", "estado": "aberto"}]
    html, _, _ = _aba(extracao, anteriores=ant, anterior=date(2026, 10, 29))
    assert "▼ melhorou (era Médio)" in html


def test_painel_completo_tem_abas_e_continua_autocontido(extracao):
    pasta = extracao(_cenario())
    d = carregar(pasta)
    aba, _, _ = _aba(extracao)
    html = gerar_html(linhas_relatorio(d, HOJE), HOJE, "x", riscos_html=aba)
    assert 'aria-controls="aba-radar"' in html and 'aria-controls="aba-riscos"' in html
    assert 'id="aba-riscos"' in html and 'id="aba-radar"' in html
    assert html.lower().count("<script") == 1 and "http://" not in html and "https://" not in html


def test_causa_provavel_no_bloco_escalar_escapada_e_com_aviso(extracao, monkeypatch):
    import riscos.painel as painel
    d = carregar(extracao(_cenario()))
    riscos = montar(d, HOJE)
    linhas = linhas_csv(riscos, d, HOJE, [])
    causas = {1: ("Atrasado <b>há</b> 9 semanas & sem dono.", ["Prazo: data alvo vencida"])}

    monkeypatch.setattr(painel, "NARRATIVAS_APROVADAS", False)
    html = gerar_aba(linhas, [], None, causas)
    assert "<b>Causa provável:</b> Atrasado &lt;b&gt;há&lt;/b&gt; 9 semanas &amp; sem dono." in html
    assert "<li>Prazo: data alvo vencida</li>" in html
    assert "Explicação gerada por IA — em validação" in html

    monkeypatch.setattr(painel, "NARRATIVAS_APROVADAS", True)
    assert "em validação" not in gerar_aba(linhas, [], None, causas)
    assert "Causa provável" not in gerar_aba(linhas, [], None)
    assert "em validação" not in gerar_aba(linhas, [], None)
