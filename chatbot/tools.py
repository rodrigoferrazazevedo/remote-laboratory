from __future__ import annotations

from typing import Any, Dict

import httpx
from langchain_core.tools import Tool

from .settings import settings


class APIClient:
    def __init__(self) -> None:
        self.base_url = settings.api_base
        self._client = httpx.Client(base_url=self.base_url, timeout=10)

    def list_experiments(self) -> Any:
        return self._request("GET", "/experiments")

    def get_experiment(self, experiment_id: int) -> Any:
        return self._request("GET", f"/experiments/{experiment_id}")

    def create_experiment(self, payload: Dict[str, Any]) -> Any:
        return self._request("POST", "/experiments", json=payload)

    def update_experiment(self, experiment_id: int, payload: Dict[str, Any]) -> Any:
        return self._request("PUT", f"/experiments/{experiment_id}", json=payload)

    def delete_experiment(self, experiment_id: int) -> Any:
        return self._request("DELETE", f"/experiments/{experiment_id}")

    def list_ground_truth(self) -> Any:
        return self._request("GET", "/ground-truth")

    def create_ground_truth(self, payload: Dict[str, Any]) -> Any:
        return self._request("POST", "/ground-truth", json=payload)

    def delete_ground_truth(self, pattern_id: int) -> Any:
        return self._request("DELETE", f"/ground-truth/{pattern_id}")

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()


def build_tools(client: APIClient):
    return [
        Tool(
            name="list_experiments",
            func=lambda *_args, **_kwargs: client.list_experiments(),
            description="Lista todos os experimentos cadastrados",
        ),
        Tool(
            name="create_experiment",
            func=lambda payload, *_args, **_kwargs: client.create_experiment(payload),
            description="Cria um experimento. Espera dict com experiment_name, ip_profinet, rack_profinet, slot_profinet, db_number_profinet, num_of_inputs, num_of_outputs.",
        ),
        Tool(
            name="delete_experiment",
            func=lambda experiment_id, *_args, **_kwargs: client.delete_experiment(int(experiment_id)),
            description="Remove um experimento existente. Informe o ID.",
        ),
        Tool(
            name="list_ground_truth",
            func=lambda *_args, **_kwargs: client.list_ground_truth(),
            description="Lista padrões cadastrados do professor.",
        ),
        Tool(
            name="create_ground_truth",
            func=lambda payload, *_args, **_kwargs: client.create_ground_truth(payload),
            description="Cria padrão do professor. Espera dict com experiment_name e ground_truth.",
        ),
        Tool(
            name="delete_ground_truth",
            func=lambda pattern_id, *_args, **_kwargs: client.delete_ground_truth(int(pattern_id)),
            description="Remove padrão do professor pelo ID.",
        ),
    ]
