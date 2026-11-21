"""Extrai work items, links/hierarquia e wiki de um projeto do Azure DevOps para CSV.

    python -m extrator              # tudo
    python -m extrator workitems    # só work items, links e hierarquia
    python -m extrator wiki         # só wiki
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from . import config, wiki, workitems
from .client import ADOClient
from .saida import Tabela

ETAPAS = {"workitems": workitems.extrair, "wiki": wiki.extrair}


def main() -> None:
    p = argparse.ArgumentParser(prog="extrator")
    p.add_argument("etapas", nargs="*", metavar="etapa", help=f"{' | '.join(ETAPAS)} (padrão: todas)")
    args = p.parse_args()
    args.etapas = args.etapas or list(ETAPAS)
    if invalidas := set(args.etapas) - set(ETAPAS):
        p.error(f"etapa desconhecida: {', '.join(sorted(invalidas))}")

    cfg = config.carregar()
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = cfg.out_dir / cfg.projeto / carimbo
    destino.mkdir(parents=True)
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(cfg.log_dir / f"{carimbo}.log", encoding="utf-8")],
    )
    log = logging.getLogger("extrator")
    log.info("Projeto %s/%s -> %s", cfg.org, cfg.projeto, destino)

    cli = ADOClient(cfg)
    with Tabela(destino / "_manifesto.csv", ["etapa", "arquivo", "linhas", "segundos"], cfg.encoding) as man:
        for etapa in args.etapas:
            inicio = time.monotonic()
            contagem = ETAPAS[etapa](cli, destino)
            duracao = round(time.monotonic() - inicio, 1)
            for arquivo, linhas in contagem.items():
                man.escrever({"etapa": etapa, "arquivo": arquivo, "linhas": linhas, "segundos": duracao})
                log.info("%-26s %8d linhas", arquivo, linhas)
            log.info("Etapa %s concluída em %ss", etapa, duracao)
    log.info("Fim: %s", destino)


if __name__ == "__main__":
    main()
