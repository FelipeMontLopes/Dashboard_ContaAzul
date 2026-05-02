from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


def mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return "***"
    return f"{token[:6]}...{token[-3:]}"


@dataclass
class ContaAzulAPIError(Exception):
    status_code: int
    message: str
    response_text: str | None = None

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.message}"


class ContaAzulClient:
    def __init__(
        self,
        base_url: str,
        access_token: str,
        timeout: int = 30,
        max_retries: int = 2,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ValueError("base_url é obrigatório.")
        if not access_token or not access_token.strip():
            raise ValueError("access_token é obrigatório.")

        self.base_url = base_url.rstrip("/")
        self.access_token = access_token.strip()
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.session = requests.Session()

        logger.info(
            "ContaAzulClient inicializado base_url=%s token=%s",
            self.base_url,
            mask_token(self.access_token),
        )

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | list | None = None) -> Any:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict | list | None = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | list | None = None,
    ) -> Any:
        clean_path = (path or "").lstrip("/")
        url = f"{self.base_url}/{clean_path}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        last_response: requests.Response | None = None
        max_attempts = self.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                logger.error("Falha de rede method=%s url=%s erro=%s", method, url, str(exc))
                raise ContaAzulAPIError(0, "Falha de conexão com a API.", str(exc)) from exc

            last_response = response
            status_code = response.status_code
            logger.info("Resposta method=%s url=%s status=%s", method, url, status_code)

            should_retry = status_code == 429 or status_code >= 500
            if should_retry and attempt < max_attempts:
                backoff_seconds = attempt
                logger.warning(
                    "Retry method=%s url=%s status=%s tentativa=%s/%s",
                    method,
                    url,
                    status_code,
                    attempt,
                    max_attempts,
                )
                time.sleep(backoff_seconds)
                continue

            if 200 <= status_code < 300:
                if not response.text:
                    return None
                try:
                    return response.json()
                except ValueError:
                    return response.text

            self._raise_for_status(response)

        # Fallback defensivo, normalmente não deve chegar aqui.
        if last_response is not None:
            self._raise_for_status(last_response)
        raise ContaAzulAPIError(0, "Erro inesperado ao processar requisição.")

    def _raise_for_status(self, response: requests.Response) -> None:
        status = response.status_code
        response_text = response.text or None
        messages = {
            400: "Requisição inválida para a API da Conta Azul.",
            401: "Não autorizado. Verifique o token de acesso.",
            403: "Acesso proibido para este recurso.",
            404: "Recurso não encontrado na API da Conta Azul.",
            429: "Limite de requisições excedido na API da Conta Azul.",
        }

        if status in messages:
            raise ContaAzulAPIError(status, messages[status], response_text)
        if status >= 500:
            raise ContaAzulAPIError(
                status,
                "Erro interno da API da Conta Azul. Tente novamente mais tarde.",
                response_text,
            )
        raise ContaAzulAPIError(status, "Erro inesperado ao chamar a API da Conta Azul.", response_text)
