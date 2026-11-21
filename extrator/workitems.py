"""Work items, links e hierarquia do projeto.

Uma única passada pelos work items alimenta todas as tabelas:
    campos.csv               metadados dos campos (referência, nome, tipo)
    tipos_relacao.csv        tipos de link existentes na organização
    workitems.csv            uma linha por work item, campos principais
    workitem_textos.csv      campos HTML (descrição, critérios de aceite...) em HTML e texto
    workitem_campos.csv      demais campos, formato longo (id, campo, valor)
    workitem_links.csv       uma linha por relação (work item, anexo, hyperlink, commit...)
    workitem_hierarquia.csv  pai, raiz, nível e caminho de cada work item
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .client import ADOClient
from .saida import Tabela, html_para_texto, identidade

log = logging.getLogger(__name__)

# coluna -> referência do campo. Identidades viram coluna_nome + coluna_email.
CAMPOS_PRINCIPAIS = {
    "rev": "System.Rev",
    "tipo": "System.WorkItemType",
    "titulo": "System.Title",
    "estado": "System.State",
    "motivo": "System.Reason",
    "area": "System.AreaPath",
    "iteracao": "System.IterationPath",
    "responsavel": "System.AssignedTo",
    "criado_por": "System.CreatedBy",
    "criado_em": "System.CreatedDate",
    "alterado_por": "System.ChangedBy",
    "alterado_em": "System.ChangedDate",
    "estado_alterado_em": "Microsoft.VSTS.Common.StateChangeDate",
    "ativado_em": "Microsoft.VSTS.Common.ActivatedDate",
    "resolvido_em": "Microsoft.VSTS.Common.ResolvedDate",
    "fechado_em": "Microsoft.VSTS.Common.ClosedDate",
    "fechado_por": "Microsoft.VSTS.Common.ClosedBy",
    "prioridade": "Microsoft.VSTS.Common.Priority",
    "severidade": "Microsoft.VSTS.Common.Severity",
    "risco": "Microsoft.VSTS.Common.Risk",
    "area_valor": "Microsoft.VSTS.Common.ValueArea",
    "story_points": "Microsoft.VSTS.Scheduling.StoryPoints",
    "esforco": "Microsoft.VSTS.Scheduling.Effort",
    "estimativa_original": "Microsoft.VSTS.Scheduling.OriginalEstimate",
    "trabalho_restante": "Microsoft.VSTS.Scheduling.RemainingWork",
    "trabalho_concluido": "Microsoft.VSTS.Scheduling.CompletedWork",
    "data_inicio": "Microsoft.VSTS.Scheduling.StartDate",
    "data_alvo": "Microsoft.VSTS.Scheduling.TargetDate",
    "data_fim": "Microsoft.VSTS.Scheduling.FinishDate",
    "coluna_board": "System.BoardColumn",
    "raia_board": "System.BoardLane",
    "tags": "System.Tags",
    "qtd_comentarios": "System.CommentCount",
    "parent_id": "System.Parent",
}
_IDENTIDADES = {"responsavel", "criado_por", "alterado_por", "fechado_por"}

_COLUNAS_WI = ["id"] + [
    c for col in CAMPOS_PRINCIPAIS
    for c in ((f"{col}_nome", f"{col}_email") if col in _IDENTIDADES else (col,))
]
_COLUNAS_LINK = [
    "origem_id", "tipo_rel", "nome_rel", "direcao", "categoria",
    "destino_id", "destino_no_projeto", "destino_url", "nome", "comentario",
    "tamanho_bytes", "criado_em", "travado",
]
_COLUNAS_HIER = [
    "id", "tipo", "titulo", "parent_id", "nivel", "raiz_id", "raiz_tipo",
    "caminho_ids", "caminho_tipos", "qtd_filhos",
]

_URL_WI = re.compile(r"/_apis/wit/workItems/(\d+)$", re.IGNORECASE)


def listar_ids(cli: ADOClient) -> list[int]:
    """Ids do projeto via Analytics (GET). WIQL exigiria POST; o Analytics pode
    atrasar alguns minutos em relação ao ADO, o que é aceitável para extração."""
    linhas = cli.odata("WorkItems", {"$select": "WorkItemId", "$orderby": "WorkItemId"})
    return [l["WorkItemId"] for l in linhas]


def _buscar_lote(cli: ADOClient, ids: list[int]) -> list[dict]:
    # $expand=relations já traz todos os campos; "fields" não pode ser combinado com $expand.
    params = {"ids": ",".join(map(str, ids)), "$expand": "relations", "errorPolicy": "omit"}
    return [w for w in cli.get("wit/workitems", params).json()["value"] if w]


def _valor_texto(valor) -> str:
    if isinstance(valor, dict) and "displayName" in valor:
        nome, email = identidade(valor)
        return f"{nome} <{email}>" if email else nome
    if isinstance(valor, bool):
        return str(valor).lower()
    return "" if valor is None else str(valor)


def _categoria(rel: str) -> str:
    if rel == "AttachedFile":
        return "anexo"
    if rel == "Hyperlink":
        return "hyperlink"
    if rel == "ArtifactLink":
        return "artefato"
    return "workitem"


def _hierarquia(nos: dict[int, dict]) -> list[dict]:
    filhos: dict[int, int] = {}
    for n in nos.values():
        if n["parent_id"]:
            filhos[n["parent_id"]] = filhos.get(n["parent_id"], 0) + 1

    linhas = []
    for wid, n in nos.items():
        caminho = [wid]
        atual = n["parent_id"]
        # O pai pode estar em outro projeto (fora de `nos`); a subida para nele.
        while atual and atual in nos and atual not in caminho:
            caminho.append(atual)
            atual = nos[atual]["parent_id"]
        caminho.reverse()
        raiz = caminho[0]
        linhas.append({
            "id": wid,
            "tipo": n["tipo"],
            "titulo": n["titulo"],
            "parent_id": n["parent_id"] or "",
            "nivel": len(caminho) - 1,
            "raiz_id": raiz,
            "raiz_tipo": nos[raiz]["tipo"],
            "caminho_ids": " > ".join(map(str, caminho)),
            "caminho_tipos": " > ".join(nos[i]["tipo"] for i in caminho),
            "qtd_filhos": filhos.get(wid, 0),
        })
    return linhas


def extrair(cli: ADOClient, destino: Path) -> dict[str, int]:
    enc = cli.cfg.encoding

    campos_meta = cli.get("wit/fields").json()["value"]
    campos_html = {c["referenceName"] for c in campos_meta if c.get("type") == "html"}
    nome_campo = {c["referenceName"]: c["name"] for c in campos_meta}
    with Tabela(destino / "campos.csv", ["referencia", "nome", "tipo", "somente_leitura"], enc) as t:
        for c in campos_meta:
            t.escrever({"referencia": c["referenceName"], "nome": c["name"],
                        "tipo": c.get("type", ""), "somente_leitura": c.get("readOnly", "")})

    tipos_rel = cli.get("wit/workitemrelationtypes", escopo="org").json()["value"]
    nome_rel = {t["referenceName"]: t["name"] for t in tipos_rel}
    with Tabela(destino / "tipos_relacao.csv", ["referencia", "nome", "topologia", "direcional", "habilitado"], enc) as t:
        for tr in tipos_rel:
            a = tr.get("attributes", {})
            t.escrever({"referencia": tr["referenceName"], "nome": tr["name"],
                        "topologia": a.get("topology", ""), "direcional": a.get("directional", ""),
                        "habilitado": a.get("enabled", "")})

    ids = listar_ids(cli)
    ids_projeto = set(ids)
    log.info("Work items no projeto: %d", len(ids))
    lotes = [ids[i:i + cli.cfg.batch_size] for i in range(0, len(ids), cli.cfg.batch_size)]
    ja_cobertos = set(CAMPOS_PRINCIPAIS.values()) | {"System.Id"}
    nos: dict[int, dict] = {}

    with Tabela(destino / "workitems.csv", _COLUNAS_WI, enc) as t_wi, \
         Tabela(destino / "workitem_textos.csv", ["id", "campo", "nome_campo", "html", "texto"], enc) as t_txt, \
         Tabela(destino / "workitem_campos.csv", ["id", "campo", "nome_campo", "valor"], enc) as t_cmp, \
         Tabela(destino / "workitem_links.csv", _COLUNAS_LINK, enc) as t_lnk, \
         ThreadPoolExecutor(cli.cfg.max_workers) as pool:

        # map() devolve na ordem dos lotes, então a escrita fica no thread principal.
        for n_lote, itens in enumerate(pool.map(lambda l: _buscar_lote(cli, l), lotes), 1):
            for wi in itens:
                wid, f = wi["id"], wi["fields"]
                linha = {"id": wid}
                for col, ref in CAMPOS_PRINCIPAIS.items():
                    if col in _IDENTIDADES:
                        linha[f"{col}_nome"], linha[f"{col}_email"] = identidade(f.get(ref))
                    else:
                        linha[col] = f.get(ref, "")
                t_wi.escrever(linha)

                for ref, valor in f.items():
                    if ref in ja_cobertos or valor in (None, ""):
                        continue
                    if ref in campos_html:
                        t_txt.escrever({"id": wid, "campo": ref, "nome_campo": nome_campo.get(ref, ref),
                                        "html": valor, "texto": html_para_texto(valor)})
                    else:
                        t_cmp.escrever({"id": wid, "campo": ref, "nome_campo": nome_campo.get(ref, ref),
                                        "valor": _valor_texto(valor)})

                for rel in wi.get("relations") or []:
                    tipo, a = rel["rel"], rel.get("attributes", {})
                    m = _URL_WI.search(rel["url"])
                    destino_id = int(m.group(1)) if m else ""
                    t_lnk.escrever({
                        "origem_id": wid,
                        "tipo_rel": tipo,
                        "nome_rel": nome_rel.get(tipo, a.get("name", "")),
                        "direcao": "forward" if tipo.endswith("-Forward") else "reverse" if tipo.endswith("-Reverse") else "",
                        "categoria": _categoria(tipo),
                        "destino_id": destino_id,
                        "destino_no_projeto": (destino_id in ids_projeto) if destino_id else "",
                        "destino_url": rel["url"],
                        "nome": a.get("name", ""),
                        "comentario": a.get("comment", ""),
                        "tamanho_bytes": a.get("resourceSize", ""),
                        "criado_em": a.get("authorizedDate", ""),
                        "travado": a.get("isLocked", ""),
                    })

                nos[wid] = {"tipo": f.get("System.WorkItemType", ""), "titulo": f.get("System.Title", ""),
                            "parent_id": f.get("System.Parent")}
            if n_lote % 25 == 0 or n_lote == len(lotes):
                log.info("Work items: lote %d/%d (%d itens)", n_lote, len(lotes), len(nos))

        contagem = {"workitems.csv": t_wi.linhas, "workitem_textos.csv": t_txt.linhas,
                    "workitem_campos.csv": t_cmp.linhas, "workitem_links.csv": t_lnk.linhas}

    with Tabela(destino / "workitem_hierarquia.csv", _COLUNAS_HIER, enc) as t:
        for linha in _hierarquia(nos):
            t.escrever(linha)
        contagem["workitem_hierarquia.csv"] = t.linhas

    if len(nos) != len(ids):
        log.warning("%d ids listados, %d retornados (excluídos durante a extração?)", len(ids), len(nos))
    return contagem
