"""Wikis do projeto e o conteúdo de cada página.

    wikis.csv           wikis do projeto (de projeto e de código)
    wiki_paginas.csv    uma linha por página, com o markdown completo
    wiki_referencias.csv  menções extraídas do markdown: work items, outras páginas, URLs
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

from .client import ADOClient
from .saida import Tabela

log = logging.getLogger(__name__)

_COLUNAS_PAG = [
    "wiki_id", "wiki_nome", "pagina_id", "caminho", "titulo", "pai_caminho",
    "ordem", "eh_pai", "git_caminho", "url", "tamanho", "conteudo",
]

# "#123" no markdown do ADO vira link para o work item 123.
_REF_WI = re.compile(r"(?<![\w&/#])#(\d{1,7})\b")
_REF_WI_URL = re.compile(r"_workitems/edit/(\d+)", re.IGNORECASE)
_LINK_MD = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_URL = re.compile(r"https?://[^\s)\]>\"']+")


def _achatar(no: dict, pai: str, saida: list[dict]) -> None:
    saida.append({"caminho": no["path"], "pai": pai, "ordem": no.get("order", ""),
                  "eh_pai": no.get("isParentPage", False), "git": no.get("gitItemPath", "")})
    for filho in no.get("subPages") or []:
        _achatar(filho, no["path"], saida)


def _referencias(pagina_id, conteudo: str) -> list[dict]:
    refs: dict[tuple[str, str], None] = {}
    for m in _REF_WI.finditer(conteudo):
        refs[("workitem", m.group(1))] = None
    for m in _REF_WI_URL.finditer(conteudo):
        refs[("workitem", m.group(1))] = None
    for m in _LINK_MD.finditer(conteudo):
        alvo = m.group(1)
        if alvo.startswith(("http://", "https://", "mailto:", "#")) or "_workitems/edit" in alvo:
            continue
        refs[("pagina", unquote(alvo.split("#")[0]).replace("-", " "))] = None
    for m in _URL.finditer(conteudo):
        if "_workitems/edit" not in m.group(0):
            refs[("url", m.group(0).rstrip(".,;"))] = None
    return [{"pagina_id": pagina_id, "tipo": t, "alvo": a} for t, a in refs]


def extrair(cli: ADOClient, destino: Path) -> dict[str, int]:
    enc = cli.cfg.encoding
    projeto_id = cli.get(f"projects/{cli.cfg.projeto}", escopo="org").json()["id"]
    # Filtra por projectId para não trazer wikis de outros projetos da organização.
    wikis = [w for w in cli.get("wiki/wikis").json()["value"] if w["projectId"] == projeto_id]

    with Tabela(destino / "wikis.csv", ["wiki_id", "nome", "tipo", "repositorio_id", "pasta", "versao"], enc) as t:
        for w in wikis:
            t.escrever({"wiki_id": w["id"], "nome": w["name"], "tipo": w["type"],
                        "repositorio_id": w.get("repositoryId", ""), "pasta": w.get("mappedPath", ""),
                        "versao": ", ".join(v["version"] for v in w.get("versions") or [])})

    with Tabela(destino / "wiki_paginas.csv", _COLUNAS_PAG, enc) as t_pag, \
         Tabela(destino / "wiki_referencias.csv", ["pagina_id", "tipo", "alvo"], enc) as t_ref, \
         ThreadPoolExecutor(cli.cfg.max_workers) as pool:
        for w in wikis:
            params = {}
            if w["type"] == "codeWiki" and w.get("versions"):
                params = {"versionDescriptor.version": w["versions"][0]["version"],
                          "versionDescriptor.versionType": "branch"}
            base = f"wiki/wikis/{w['id']}/pages"
            arvore = cli.get(base, {**params, "path": "/", "recursionLevel": "full"}).json()
            paginas: list[dict] = []
            _achatar(arvore, "", paginas)
            # A raiz "/" é só o contêiner da árvore, sem conteúdo próprio.
            paginas = [p for p in paginas if p["caminho"] != "/"]
            log.info("Wiki %s: %d páginas", w["name"], len(paginas))

            # A árvore não traz o id das páginas; a busca por caminho traz id e conteúdo.
            def baixar(p: dict) -> tuple[dict, dict | None]:
                try:
                    return p, cli.get(base, {**params, "path": p["caminho"], "includeContent": "true"}).json()
                except Exception as e:  # uma página com problema não derruba a wiki inteira
                    log.error("Página %s: %s", p["caminho"], e)
                    return p, None

            for n, (p, dados) in enumerate(pool.map(baixar, paginas), 1):
                dados = dados or {}
                conteudo = dados.get("content", "")
                t_pag.escrever({
                    "wiki_id": w["id"], "wiki_nome": w["name"], "pagina_id": dados.get("id", ""),
                    "caminho": p["caminho"], "titulo": p["caminho"].rsplit("/", 1)[-1],
                    "pai_caminho": p["pai"] if p["pai"] != "/" else "", "ordem": p["ordem"],
                    "eh_pai": p["eh_pai"], "git_caminho": p["git"],
                    "url": dados.get("remoteUrl", ""), "tamanho": len(conteudo), "conteudo": conteudo,
                })
                for ref in _referencias(dados.get("id", ""), conteudo):
                    t_ref.escrever(ref)
                if n % 200 == 0:
                    log.info("Wiki %s: %d/%d páginas", w["name"], n, len(paginas))

        return {"wikis.csv": len(wikis), "wiki_paginas.csv": t_pag.linhas,
                "wiki_referencias.csv": t_ref.linhas}
