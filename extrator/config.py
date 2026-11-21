"""Configuração lida do .env."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    org: str
    projeto: str
    pat: str
    api_version: str
    analytics_version: str
    out_dir: Path
    log_dir: Path
    max_workers: int
    batch_size: int
    connect_timeout: float
    read_timeout: float
    max_retries: int
    encoding: str
    log_level: str


def carregar() -> Config:
    load_dotenv()
    faltando = [k for k in ("ADO_ORG", "ADO_PROJECT", "ADO_PAT") if not os.getenv(k)]
    if faltando:
        raise SystemExit(f"Variáveis obrigatórias ausentes no .env: {', '.join(faltando)}")
    return Config(
        org=os.environ["ADO_ORG"],
        projeto=os.environ["ADO_PROJECT"],
        pat=os.environ["ADO_PAT"],
        api_version=os.getenv("ADO_API_VERSION", "7.1"),
        analytics_version=os.getenv("ADO_ANALYTICS_VERSION", "v4.0-preview"),
        out_dir=Path(os.getenv("OUT_DIR", "out")),
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
        max_workers=int(os.getenv("MAX_WORKERS", "6")),
        # A API de batch recusa mais de 200 ids por chamada.
        batch_size=min(int(os.getenv("BATCH_SIZE", "200")), 200),
        connect_timeout=float(os.getenv("CONNECT_TIMEOUT_S", "10")),
        read_timeout=float(os.getenv("READ_TIMEOUT_S", "180")),
        max_retries=int(os.getenv("MAX_RETRIES", "5")),
        encoding=os.getenv("CSV_ENCODING", "utf-8-sig"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
