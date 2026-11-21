"""Gera uma extração sintética, no mesmo formato dos CSVs do `extrator`, para demonstrar o painel sem dados reais.

    python demo/gerar_extracao.py
    python -m radar relatorio --extracao demo/dados/sintetica --saida demo/painel --hoje 2026-11-17

Projeto, programas, pessoas, títulos e ids são inventados. Cada Epic segue um perfil escolhido para
exercitar uma parte do painel (farol verde/amarelo/vermelho, atraso, escopo vazio, falta de dono,
qualidade, dependência entre programas). A mesma semente gera sempre os mesmos arquivos.
"""
import argparse
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

REF = date(2026, 11, 17)          # use esta data em --hoje
PROJETO = "Atlas"
PESSOAS = {
    "Rede Norte": ["Ana Souza", "Caio Prado", "Davi Rocha"],
    "Obras Sul": ["Bruna Lima", "Elisa Nunes", "Fabio Teles"],
    "Plataforma Digital Base": ["Gilda Reis", "Hugo Maia", "Iara Pinto"],
    "Canais": ["Joel Farias", "Katia Melo", "Luan Bessa"],
    "Dados Mestres": ["Mara Diniz", "Nilo Queiroz", "Olga Paes"],
}
COLUNAS_WI = ["id", "tipo", "titulo", "estado", "area", "responsavel_nome", "criado_em",
              "fechado_em", "data_inicio", "data_alvo", "parent_id"]
COLUNAS_HIER = ["id", "tipo", "titulo", "parent_id", "nivel", "raiz_id", "raiz_tipo",
                "caminho_ids", "caminho_tipos", "qtd_filhos"]


@dataclass(frozen=True)
class Perfil:
    """Como o Epic se comportou até REF."""
    alvo_dias: int | None = 45     # data alvo em dias a partir de REF (negativo = vencida; None = sem data)
    restante: int = 8              # itens abertos em REF
    entrega: float = 2.5           # itens entregues por semana, em média
    entrada: float = 0.3           # itens novos por semana, em média
    semanas: int = 24              # idade do Epic
    parada: int = 0                # semanas mais recentes sem nenhuma entrega
    surto: int = 0                 # itens criados de uma vez nas últimas 3 semanas
    sem_dono: float = 0.0          # fração dos itens restantes sem responsável
    bugs: int = 0                  # itens restantes que são Bug
    faults: int = 0                # Faults abertas
    com_dono: bool = True          # o Epic tem responsável
    feature_vencida: bool = False  # uma Feature com data alvo vencida
    concluido: bool = False


VERDE = Perfil(alvo_dias=42, restante=6, entrega=3.0)
AMARELO = Perfil(alvo_dias=42, restante=12, entrega=2.2, entrada=0.2)
LENTO = Perfil(alvo_dias=35, restante=30, entrega=1.5, entrada=0.5)
SEM_DATA = Perfil(alvo_dias=None, restante=10, entrega=1.5)
CONCLUIDO = Perfil(alvo_dias=-30, restante=0, entrega=3.0, concluido=True)

EPICS: list[tuple[str, str, str, Perfil]] = [   # (chave, título, programa, perfil)
    ("pedidos", "Portal de pedidos", "Rede Norte", VERDE),
    ("rotas", "Roteirização de entregas", "Rede Norte", AMARELO),
    ("rastreio", "Rastreio de cargas", "Rede Norte", LENTO),
    ("patio", "Gestão de pátio", "Rede Norte", Perfil(alvo_dias=-20, restante=10, entrega=1.2, feature_vencida=True)),
    ("voz", "Conferência por voz", "Rede Norte", SEM_DATA),
    ("transportadoras", "Painel de transportadoras", "Rede Norte", CONCLUIDO),
    ("docas", "Agendamento de docas", "Rede Norte", Perfil(alvo_dias=21, restante=35, entrega=1.5, entrada=0.6)),
    ("ativos", "Padrão de ativos", "Obras Sul", Perfil(alvo_dias=-75, restante=14, entrega=0.8, semanas=34)),
    ("equipamentos", "Cadastro de equipamentos", "Obras Sul", Perfil(alvo_dias=30, restante=15, entrega=2.0, parada=6)),
    ("checklists", "Checklists de campo", "Obras Sul", VERDE),
    ("foto", "Inspeção por foto", "Obras Sul", Perfil(alvo_dias=50, restante=0, entrega=0, entrada=0)),
    ("mapa", "Mapa de instalações", "Obras Sul",
     Perfil(alvo_dias=40, restante=34, entrega=1.4, sem_dono=0.6, com_dono=False)),
    ("normas", "Biblioteca de normas", "Obras Sul", CONCLUIDO),
    ("ordens", "Ordens de serviço móveis", "Obras Sul", Perfil(alvo_dias=38, restante=18, entrega=1.6)),
    ("login", "Login único", "Plataforma Digital Base", VERDE),
    ("eventos", "Barramento de eventos", "Plataforma Digital Base",
     Perfil(alvo_dias=45, restante=20, entrega=2.5, surto=12)),
    ("apis", "Catálogo de APIs", "Plataforma Digital Base", AMARELO),
    ("observabilidade", "Observabilidade", "Plataforma Digital Base",
     Perfil(alvo_dias=40, restante=12, entrega=2.0, bugs=4, faults=3)),
    ("esteira", "Esteira de entrega contínua", "Plataforma Digital Base", CONCLUIDO),
    ("acessos", "Gestão de acessos", "Plataforma Digital Base", Perfil(alvo_dias=-10, restante=7, entrega=1.8)),
    ("dados", "Camada de dados", "Plataforma Digital Base",
     Perfil(alvo_dias=30, restante=32, entrega=1.6, entrada=0.5, feature_vencida=True)),
    ("aplicativo", "Aplicativo do cliente", "Canais", Perfil(alvo_dias=44, restante=16, entrega=2.0)),
    ("notificacoes", "Central de notificações", "Canais", VERDE),
    ("autoatendimento", "Autoatendimento", "Canais", SEM_DATA),
    ("fidelidade", "Programa de fidelidade", "Canais", VERDE),
    ("chat", "Chat de suporte", "Canais", Perfil(alvo_dias=42, restante=11, entrega=2.0, bugs=3, faults=2)),
    ("site", "Novo site institucional", "Canais", CONCLUIDO),
    ("pesquisa", "Pesquisa de satisfação", "Canais", Perfil(alvo_dias=60, restante=9, entrega=0, semanas=10)),
    ("produtos", "Cadastro único de produtos", "Dados Mestres", LENTO),
    ("qualidade", "Qualidade de dados", "Dados Mestres", VERDE),
    ("glossario", "Glossário de negócio", "Dados Mestres", SEM_DATA),
    ("legado", "Migração de legado", "Dados Mestres",
     Perfil(alvo_dias=-90, restante=22, entrega=0.7, semanas=36, sem_dono=0.4, com_dono=False)),
    ("paineis", "Painéis executivos", "Dados Mestres", AMARELO),
    ("fiscal", "Integração fiscal", "Dados Mestres", CONCLUIDO),
]
# (Epic predecessor, Epic que depende dele): o sucessor só começa depois de uma Feature vencida do predecessor.
DEPENDENCIAS = [("patio", "ordens"), ("dados", "aplicativo"), ("dados", "notificacoes")]


def _iso(d: date | None) -> str:
    return f"{d.isoformat()}T12:00:00Z" if d else ""


def gerar(semente: int = 42) -> tuple[list[dict], list[tuple[int, str, int]]]:
    rng = np.random.default_rng(semente)
    itens: list[dict] = []
    links: list[tuple[int, str, int]] = []
    feature_vencida: dict[str, int] = {}
    abertos: dict[str, list[int]] = {}

    def novo(tipo, titulo, area, criado, *, pai=None, estado="New", fechado=None, alvo=None, inicio=None, resp=""):
        itens.append({"id": 1001 + len(itens), "tipo": tipo, "titulo": titulo, "estado": estado, "area": area,
                      "responsavel_nome": resp, "criado_em": _iso(criado), "fechado_em": _iso(fechado),
                      "data_inicio": _iso(inicio), "data_alvo": _iso(alvo), "parent_id": pai or ""})
        return itens[-1]

    for n, (chave, titulo, programa, p) in enumerate(EPICS):
        time = PESSOAS[programa]
        area = f"{PROJETO}\\{programa}\\Time {'AB'[n % 2]}"
        segunda = REF - timedelta(days=REF.weekday())
        inicio = segunda - timedelta(weeks=p.semanas)
        fim = REF + timedelta(days=p.alvo_dias) if p.alvo_dias is not None else None
        fechado = fim - timedelta(days=int(rng.integers(0, 10))) if p.concluido else None
        epic = novo("Epic", titulo, area, inicio, estado="Done" if p.concluido else "In Progress", fechado=fechado,
                    alvo=fim, inicio=inicio, resp=time[0] if p.com_dono else "")

        features = []
        for k in range(3):
            vencida = p.feature_vencida and k == 0
            f = novo("Feature", f"{titulo}: etapa {k + 1}", area, inicio, pai=epic["id"],
                     estado="Done" if p.concluido else "In Progress", fechado=fechado,
                     alvo=REF - timedelta(days=14) if vencida else fim, resp=time[k % len(time)])
            features.append(f)
            if vencida:
                feature_vencida[chave] = f["id"]

        # Entregas e entradas por semana até o corte (REF ou o fechamento do Epic).
        corte = fechado or REF
        semanas = [inicio + timedelta(weeks=w) for w in range(p.semanas) if inicio + timedelta(weeks=w) < corte]
        entregas = rng.poisson(p.entrega, len(semanas))
        if p.parada:
            entregas[-p.parada:] = 0
        entradas = rng.poisson(p.entrada, len(semanas))
        entradas[0] = 0
        total = int(entregas.sum()) + p.restante
        iniciais = max(total - int(entradas.sum()) - p.surto, 0)

        criados = [inicio + timedelta(days=int(rng.integers(0, 5))) for _ in range(iniciais)]
        for s, qtd in zip(semanas, entradas):
            criados += [s + timedelta(days=int(rng.integers(0, 5))) for _ in range(int(qtd))]
        criados += [REF - timedelta(days=int(rng.integers(2, 20))) for _ in range(p.surto)]
        criados = sorted(c for c in criados if c < corte)[:total] if total else []

        escopo = [novo("Product Backlog Item", f"{titulo}: item {k + 1}", area, c,
                       pai=features[k % 3]["id"], resp=time[k % len(time)]) for k, c in enumerate(criados)]
        fila = list(escopo)
        for s, qtd in zip(semanas, entregas):
            prontos = [i for i in fila if i["criado_em"] < _iso(s)][:int(qtd)]
            for i in prontos:
                dia = min(s + timedelta(days=int(rng.integers(0, 5))), corte - timedelta(days=1))
                i.update(estado="Done", fechado_em=_iso(dia))
                fila.remove(i)
        if p.concluido:
            for i in fila:
                i.update(estado="Done", fechado_em=_iso(fechado - timedelta(days=1)))
            fila = []

        for i in fila[:p.bugs]:
            i["tipo"] = "Bug"
        for i in fila[len(fila) - round(p.sem_dono * len(fila)):] if p.sem_dono else []:
            i["responsavel_nome"] = ""
        for k in range(p.faults):
            novo("Fault", f"{titulo}: falha {k + 1}", area, REF - timedelta(days=int(rng.integers(3, 30))),
                 pai=fila[-1 - k]["id"], resp=time[k % len(time)])
        abertos[chave] = [i["id"] for i in fila]

    for pred, suc in DEPENDENCIAS:
        links.append((feature_vencida[pred], "Successor", abertos[suc][-1]))
    return itens, links


def gravar(pasta: Path, itens: list[dict], links: list[tuple[int, str, int]]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    por_id = {i["id"]: i for i in itens}
    filhos: dict[int, int] = {}
    for i in itens:
        if i["parent_id"]:
            filhos[i["parent_id"]] = filhos.get(i["parent_id"], 0) + 1

    def caminho(i: dict) -> list[int]:
        ids = [i["id"]]
        while pai := por_id[ids[-1]]["parent_id"]:
            ids.append(pai)
        return ids[::-1]

    def escrever(nome: str, colunas: list[str], linhas) -> None:
        with (pasta / nome).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=colunas)
            w.writeheader()
            w.writerows(linhas)

    escrever("workitems.csv", COLUNAS_WI, itens)
    hier = []
    for i in itens:
        cam = caminho(i)
        hier.append({"id": i["id"], "tipo": i["tipo"], "titulo": i["titulo"], "parent_id": i["parent_id"],
                     "nivel": len(cam) - 1, "raiz_id": cam[0], "raiz_tipo": por_id[cam[0]]["tipo"],
                     "caminho_ids": " > ".join(map(str, cam)),
                     "caminho_tipos": " > ".join(por_id[c]["tipo"] for c in cam), "qtd_filhos": filhos.get(i["id"], 0)})
    escrever("workitem_hierarquia.csv", COLUNAS_HIER, hier)
    escrever("workitem_links.csv", ["origem_id", "nome_rel", "categoria", "destino_id"],
             [{"origem_id": o, "nome_rel": n, "categoria": "workitem", "destino_id": d} for o, n, d in links])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default=str(Path(__file__).parent / "dados" / "sintetica"), help="pasta da extração")
    p.add_argument("--semente", type=int, default=42)
    args = p.parse_args()
    itens, links = gerar(args.semente)
    gravar(Path(args.saida), itens, links)
    print(f"{len(itens)} work items ({sum(i['tipo'] == 'Epic' for i in itens)} Epics) e {len(links)} dependências "
          f"em {args.saida}. Use --hoje {REF.isoformat()}.")


if __name__ == "__main__":
    main()
