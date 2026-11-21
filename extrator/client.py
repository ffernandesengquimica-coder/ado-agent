"""Cliente HTTP do Azure DevOps, somente leitura, com retry e respeito ao rate limit.

Só existe GET. Qualquer outro método é recusado antes de sair da máquina,
mesmo endpoints de consulta que usam POST (wiql, workitemsbatch).
"""
import logging
import time
from urllib.parse import quote

import requests

from .config import Config

log = logging.getLogger(__name__)

_RETENTAVEIS = {429, 500, 502, 503, 504}


class _SessaoSomenteLeitura(requests.Session):
    def request(self, method, url, *args, **kwargs):
        if method.upper() != "GET":
            raise PermissionError(f"Extrator é somente leitura: {method} {url} bloqueado")
        return super().request(method, url, *args, **kwargs)


class ADOClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.org_url = f"https://dev.azure.com/{cfg.org}"
        self.projeto_url = f"{self.org_url}/{quote(cfg.projeto)}"
        self.analytics_url = (
            f"https://analytics.dev.azure.com/{cfg.org}/{quote(cfg.projeto)}/_odata/{cfg.analytics_version}"
        )
        self.sessao = _SessaoSomenteLeitura()
        self.sessao.auth = ("", cfg.pat)
        self.sessao.headers["Accept"] = "application/json"

    def get(self, caminho: str, params: dict | None = None, *, escopo: str = "projeto") -> requests.Response:
        base = self.projeto_url if escopo == "projeto" else self.org_url
        params = {"api-version": self.cfg.api_version, **(params or {})}
        return self._get(f"{base}/_apis/{caminho.lstrip('/')}", params)

    def odata(self, entidade: str, params: dict) -> list[dict]:
        """Lê uma entidade do Analytics seguindo @odata.nextLink até o fim."""
        linhas: list[dict] = []
        url, p = f"{self.analytics_url}/{entidade}", params
        while url:
            d = self._get(url, p).json()
            linhas.extend(d["value"])
            url, p = d.get("@odata.nextLink"), None  # o nextLink já carrega os parâmetros
        return linhas

    def _get(self, url: str, params: dict | None) -> requests.Response:
        timeout = (self.cfg.connect_timeout, self.cfg.read_timeout)

        for tentativa in range(self.cfg.max_retries + 1):
            try:
                r = self.sessao.get(url, params=params, timeout=timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                if tentativa == self.cfg.max_retries:
                    raise
                espera = 2 ** tentativa
                log.warning("GET %s falhou (%s); nova tentativa em %ss", url, e, espera)
                time.sleep(espera)
                continue

            # O ADO manda Retry-After também em respostas 200 quando está
            # atrasando o cliente; ignorar isso leva a 429 logo em seguida.
            retry_after = r.headers.get("Retry-After")
            if r.status_code in _RETENTAVEIS and tentativa < self.cfg.max_retries:
                espera = float(retry_after) if retry_after else 2 ** tentativa
                log.warning("GET %s -> %s; nova tentativa em %ss", url, r.status_code, espera)
                time.sleep(espera)
                continue
            if r.status_code in (401, 403):
                raise PermissionError(f"{r.status_code} em {url}: verifique escopos e validade do PAT")
            r.raise_for_status()
            if retry_after:
                time.sleep(float(retry_after))
            return r
        raise RuntimeError("inalcançável")
