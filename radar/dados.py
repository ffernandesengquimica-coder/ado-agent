"""Carrega uma extração e monta os Epics e o escopo de cada um.

Escopo de um Epic = descendentes dos tipos entregáveis (TIPOS_ESCOPO), não Removed,
cujo Epic mais próximo acima é ele. Tasks e Test Cases ficam de fora: são
subdivisões ou artefatos de teste e contariam o mesmo trabalho duas vezes.

Para o Agente de Riscos, carrega também as Faults de cada Epic e as dependências
(links Successor) entre itens abertos de Epics diferentes.
"""
import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

TIPOS_ESCOPO = {"Product Backlog Item", "Bug", "Habilitator", "Spike"}
ESTADOS_FECHADOS = {"Done", "Removed", "Closed"}


@dataclass(frozen=True)
class Item:
    id: int
    tipo: str
    titulo: str
    estado: str
    area: str
    responsavel: str
    criado: date
    fechado: date | None
    inicio: date | None
    alvo: date | None


@dataclass(frozen=True)
class Dados:
    epics: dict[int, Item]
    escopo: dict[int, list[Item]]    # epic_id -> itens de escopo
    features: dict[int, list[Item]]  # epic_id -> Features (para os motivos)
    epic_de: dict[int, int] = field(default_factory=dict)           # item -> Epic mais próximo (o próprio, se Epic)
    faults: dict[int, list[Item]] = field(default_factory=dict)     # epic_id -> Faults não Removed
    dependencias: list[tuple[Item, Item]] = field(default_factory=list)  # (predecessor, sucessor)


def _data(texto: str) -> date | None:
    return date.fromisoformat(texto[:10]) if texto else None


def _ler(caminho: Path) -> list[dict]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ultima_extracao(out_dir: Path, projeto: str) -> Path:
    # Os nomes são carimbos UTC (AAAAMMDDTHHMMSSZ), então a ordem alfabética é a cronológica.
    pastas = sorted(p for p in (out_dir / projeto).glob("*") if p.is_dir())
    if not pastas:
        raise FileNotFoundError(f"Nenhuma extração em {out_dir / projeto}")
    return pastas[-1]


def carregar(pasta: Path) -> Dados:
    itens = {
        int(r["id"]): Item(
            id=int(r["id"]), tipo=r["tipo"], titulo=r["titulo"], estado=r["estado"], area=r["area"],
            responsavel=r["responsavel_nome"], criado=_data(r["criado_em"]), fechado=_data(r["fechado_em"]),
            inicio=_data(r["data_inicio"]), alvo=_data(r["data_alvo"]),
        )
        for r in _ler(pasta / "workitems.csv")
    }
    epics = {i: it for i, it in itens.items() if it.tipo == "Epic"}
    escopo: dict[int, list[Item]] = {}
    features: dict[int, list[Item]] = {}
    faults: dict[int, list[Item]] = {}
    epic_de = {i: i for i in epics}
    for r in _ler(pasta / "workitem_hierarquia.csv"):
        it = itens[int(r["id"])]
        ancestrais = [int(a) for a in r["caminho_ids"].split(" > ")[:-1]]
        epic_id = next((a for a in reversed(ancestrais) if a in epics), None)
        if epic_id is None:
            continue
        if it.tipo != "Epic":
            epic_de[it.id] = epic_id
        if it.tipo == "Feature":
            features.setdefault(epic_id, []).append(it)
        elif it.tipo in TIPOS_ESCOPO and it.estado != "Removed":
            escopo.setdefault(epic_id, []).append(it)
        elif it.tipo == "Fault" and it.estado != "Removed":
            faults.setdefault(epic_id, []).append(it)
    return Dados(epics=epics, escopo=escopo, features=features, epic_de=epic_de, faults=faults,
                 dependencias=_dependencias(pasta / "workitem_links.csv", itens, epic_de))


def _dependencias(caminho: Path, itens: dict[int, Item], epic_de: dict[int, int]) -> list[tuple[Item, Item]]:
    """Pares (predecessor, sucessor) abertos, com o sucessor sob um Epic e o predecessor fora dele.

    No ADO, o link `Successor` gravado em P aponta para S: S só começa depois de P. A extração
    traz também o `Predecessor` inverso; ler só um lado evita contar o par duas vezes.
    """
    if not caminho.exists():
        return []
    aberto = lambda it: it.estado not in ESTADOS_FECHADOS
    pares = set()
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["nome_rel"] != "Successor" or r["categoria"] != "workitem":
                continue
            p, s = itens.get(int(r["origem_id"])), itens.get(int(r["destino_id"]))
            if p is None or s is None or not (aberto(p) and aberto(s)):
                continue
            epic_s = epic_de.get(s.id)
            if epic_s is not None and epic_de.get(p.id) != epic_s:
                pares.add((p.id, s.id))
    return [(itens[p], itens[s]) for p, s in sorted(pares)]
