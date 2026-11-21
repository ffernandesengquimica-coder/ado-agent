import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import item
from radar.__main__ import montar_parser


def test_help_lista_subcomandos():
    r = subprocess.run([sys.executable, "-m", "radar", "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "relatorio" in r.stdout and "backtest" in r.stdout


def test_relatorio_aceita_opcoes_comuns():
    args = montar_parser().parse_args(["relatorio", "--extracao", "x", "--hoje", "2026-11-05", "--semente", "7"])
    assert (args.comando, args.extracao, str(args.hoje), args.semente) == ("relatorio", "x", "2026-11-05", 7)


def test_backtest_aceita_cortes():
    args = montar_parser().parse_args(["backtest", "--cortes", "2026-07-06,2026-08-03"])
    assert [str(c) for c in args.cortes] == ["2026-07-06", "2026-08-03"]


def test_subcomando_obrigatorio():
    with pytest.raises(SystemExit):
        montar_parser().parse_args([])


def test_backtest_grava_csvs_em_relatorios(extracao, tmp_path):
    pasta = extracao([item(1, "Epic", alvo="2026-09-30"), item(2, "Product Backlog Item", pai=1)])
    raiz = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "radar", "backtest", "--extracao", str(pasta), "--hoje", "2026-11-05",
         "--cortes", "2026-08-03"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(raiz), "PYTHONIOENCODING": "utf-8"},
    )
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "relatorios" / "backtest-2026-11-05.csv").exists()
    assert (tmp_path / "relatorios" / "backtest-2026-11-05-detalhe.csv").exists()
    assert "Portão" in r.stdout


def test_relatorio_grava_csv_e_reconcilia(extracao, tmp_path):
    pasta = extracao([item(1, "Epic", alvo="2026-12-30"), item(2, "Epic"),
                      item(3, "Epic", estado="Done", fechado="2026-09-01")])
    raiz = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "-m", "radar", "relatorio", "--extracao", str(pasta), "--hoje", "2026-11-05"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(raiz), "PYTHONIOENCODING": "utf-8"},
    )
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "relatorios" / "radar-2026-11-05.csv").exists()
    assert (tmp_path / "relatorios" / "radar-2026-11-05.html").exists()
    assert "2 Epics abertos = vermelho 1 + amarelo 0 + ja_atrasado 0 + sem_como_prever 1 + verde 0" in r.stdout


def _rodar_relatorio(pasta, cwd, hoje):
    raiz = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "-m", "radar", "relatorio", "--extracao", str(pasta), "--hoje", hoje],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONPATH": str(raiz), "PYTHONIOENCODING": "utf-8"},
    )


def test_relatorio_grava_registro_de_riscos_com_movimento(extracao, tmp_path):
    import csv
    pasta = extracao([item(1, "Epic", alvo="2026-12-30"), item(2, "Epic")])
    r = _rodar_relatorio(pasta, tmp_path, "2026-11-05")
    assert r.returncode == 0, r.stderr
    primeiro = tmp_path / "relatorios" / "riscos-2026-11-05.csv"
    with primeiro.open(encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    assert [(l["risco_id"], l["movimento"]) for l in linhas] == [("R-1-ESCOPO", "novo"), ("R-2-GOVERNANCA", "novo")]
    assert "Riscos: 2 em 2 Epics" in r.stdout and "anterior: nenhum" in r.stdout

    # Rodar de novo no mesmo dia não usa o próprio arquivo como "anterior".
    conteudo = primeiro.read_bytes()
    assert _rodar_relatorio(pasta, tmp_path, "2026-11-05").returncode == 0
    assert primeiro.read_bytes() == conteudo

    # Uma semana depois, o de 05/11 é o anterior.
    r = _rodar_relatorio(pasta, tmp_path, "2026-11-12")
    assert "anterior: riscos-2026-11-05.csv" in r.stdout
    with (tmp_path / "relatorios" / "riscos-2026-11-12.csv").open(encoding="utf-8-sig") as f:
        assert {l["movimento"] for l in csv.DictReader(f)} == {"igual"}


def test_relatorio_sem_modelo_pula_narrativas(extracao, tmp_path):
    pasta = extracao([item(1, "Epic", alvo="2026-09-01", responsavel=""),
                      *[item(100 + k, "Product Backlog Item", pai=1, responsavel="") for k in range(31)]])
    r = _rodar_relatorio(pasta, tmp_path, "2026-11-05")
    assert r.returncode == 0, r.stderr
    assert "Narrativas: puladas (OPENAI_MODEL vazio no .env)" in r.stdout
    assert not list((tmp_path / "relatorios").glob("narrativas-*.csv"))
    html = (tmp_path / "relatorios" / "radar-2026-11-05.html").read_text(encoding="utf-8")
    assert "<b>Causa provável:</b>" not in html
    assert "Agente: pauta por regra" in r.stdout and "Pauta da semana" in html


def test_relatorio_sem_chave_usa_so_o_cache(extracao, tmp_path, monkeypatch):
    pasta = extracao([item(1, "Epic", alvo="2026-09-01", responsavel=""),
                      *[item(100 + k, "Product Backlog Item", pai=1, responsavel="") for k in range(31)]])
    monkeypatch.setenv("OPENAI_MODEL", "modelo-teste")
    r = _rodar_relatorio(pasta, tmp_path, "2026-11-05")
    assert r.returncode == 0, r.stderr
    assert "Narrativas: 1 Epics no Escalar = 0 válidas" in r.stdout and "só cache: OPENAI_API_KEY vazia" in r.stdout
