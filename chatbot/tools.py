from __future__ import annotations

from typing import Any, Dict

import httpx
from langchain_core.tools import StructuredTool, Tool
from pydantic import BaseModel, Field

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
    class CreateExperimentInput(BaseModel):
        experiment_name: str = Field(..., description="Nome do experimento")
        ip_profinet: str = Field(..., description="IP do PLC/Profinet")
        rack_profinet: int = Field(..., description="Rack do PLC")
        slot_profinet: int = Field(..., description="Slot do PLC")
        db_number_profinet: int = Field(..., description="DB de leitura/escrita")
        num_of_inputs: int = Field(..., description="Quantidade de entradas digitais")
        num_of_outputs: int = Field(..., description="Quantidade de saídas digitais")

    class CreateGroundTruthInput(BaseModel):
        experiment_name: str = Field(..., description="Nome do experimento já cadastrado")
        ground_truth: str = Field(..., description="Padrão do professor (texto ou JSON)")

    class DeleteIdInput(BaseModel):
        id: int = Field(..., description="ID numérico do recurso")

    return [
        Tool(
            name="list_experiments",
            func=lambda *_args, **_kwargs: client.list_experiments(),
            description="Lista todos os experimentos cadastrados",
        ),
        StructuredTool.from_function(
            name="create_experiment",
            func=lambda experiment_name, ip_profinet, rack_profinet, slot_profinet, db_number_profinet, num_of_inputs, num_of_outputs: client.create_experiment(
                {
                    "experiment_name": experiment_name,
                    "ip_profinet": ip_profinet,
                    "rack_profinet": rack_profinet,
                    "slot_profinet": slot_profinet,
                    "db_number_profinet": db_number_profinet,
                    "num_of_inputs": num_of_inputs,
                    "num_of_outputs": num_of_outputs,
                }
            ),
            args_schema=CreateExperimentInput,
            description=(
                "Cria um experimento. Informe experiment_name, ip_profinet, rack_profinet, "
                "slot_profinet, db_number_profinet, num_of_inputs, num_of_outputs."
            ),
        ),
        StructuredTool.from_function(
            name="delete_experiment",
            func=lambda id: client.delete_experiment(int(id)),
            args_schema=DeleteIdInput,
            description="Remove um experimento existente. Informe o ID.",
        ),
        Tool(
            name="list_ground_truth",
            func=lambda *_args, **_kwargs: client.list_ground_truth(),
            description="Lista padrões cadastrados do professor.",
        ),
        StructuredTool.from_function(
            name="create_ground_truth",
            func=lambda experiment_name, ground_truth: client.create_ground_truth(
                {"experiment_name": experiment_name, "ground_truth": ground_truth}
            ),
            args_schema=CreateGroundTruthInput,
            description="Cria padrão do professor. Informe experiment_name e ground_truth.",
        ),
        StructuredTool.from_function(
            name="delete_ground_truth",
            func=lambda id: client.delete_ground_truth(int(id)),
            args_schema=DeleteIdInput,
            description="Remove padrão do professor pelo ID.",
        ),
    ]
