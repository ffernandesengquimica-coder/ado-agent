"""Fábrica de extrações sintéticas: os mesmos CSVs que o `extrator` gera, com poucos itens."""
import csv
from pathlib import Path

import pytest

_COLUNAS_WI = ["id", "tipo", "titulo", "estado", "area", "responsavel_nome", "criado_em",
               "fechado_em", "data_inicio", "data_alvo", "parent_id"]
_COLUNAS_HIER = ["id", "tipo", "titulo", "parent_id", "nivel", "raiz_id", "raiz_tipo",
                 "caminho_ids", "caminho_tipos", "qtd_filhos"]


def item(id: int, tipo: str, *, pai: int | None = None, estado: str = "New",
         criado: str = "2026-03-02", fechado: str | None = None, inicio: str | None = None,
         alvo: str | None = None, responsavel: str = "Pessoa", area: str = "Atlas\\Area") -> dict:
    """Um work item como linha de workitems.csv. Datas em AAAA-MM-DD viram ISO com hora, como no ADO."""
    iso = lambda d: f"{d}T12:00:00Z" if d else ""
    return {"id": id, "tipo": tipo, "titulo": f"{tipo} {id}", "estado": estado, "area": area,
            "responsavel_nome": responsavel, "criado_em": iso(criado), "fechado_em": iso(fechado),
            "data_inicio": iso(inicio), "data_alvo": iso(alvo), "parent_id": pai or ""}


def gravar_extracao(pasta: Path, itens: list[dict], links: list[tuple[int, str, int]] = ()) -> Path:
    """`links` = (origem, nome_rel, destino), ex.: (P, "Successor", S) quando S depende de P."""
    pasta.mkdir(parents=True, exist_ok=True)
    por_id = {i["id"]: i for i in itens}

    def caminho(i: dict) -> list[int]:
        ids = [i["id"]]
        while (pai := por_id.get(ids[-1], {}).get("parent_id")) and pai in por_id:
            ids.append(pai)
        return ids[::-1]

    with (pasta / "workitems.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_COLUNAS_WI)
        w.writeheader()
        w.writerows(itens)
    with (pasta / "workitem_hierarquia.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_COLUNAS_HIER)
        w.writeheader()
        for i in itens:
            cam = caminho(i)
            w.writerow({"id": i["id"], "tipo": i["tipo"], "titulo": i["titulo"], "parent_id": i["parent_id"],
                        "nivel": len(cam) - 1, "raiz_id": cam[0], "raiz_tipo": por_id[cam[0]]["tipo"],
                        "caminho_ids": " > ".join(map(str, cam)),
                        "caminho_tipos": " > ".join(por_id[c]["tipo"] for c in cam), "qtd_filhos": 0})
    with (pasta / "workitem_links.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["origem_id", "nome_rel", "categoria", "destino_id"])
        w.writeheader()
        w.writerows({"origem_id": o, "nome_rel": n, "categoria": "workitem", "destino_id": d} for o, n, d in links)
    return pasta


@pytest.fixture
def extracao(tmp_path):
    """Chame com a lista de itens (e, opcionalmente, os links); devolve a pasta da extração."""
    return lambda itens, links=(): gravar_extracao(tmp_path / "out" / "Atlas" / "20261105T000000Z", itens, links)


@pytest.fixture(autouse=True)
def _sem_openai(monkeypatch):
    """Nenhum teste chama a OpenAI: variáveis vazias valem mais que o .env (load_dotenv não sobrescreve)."""
    for nome in ("OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.setenv(nome, "")
