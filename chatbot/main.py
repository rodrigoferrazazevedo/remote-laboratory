from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import httpx
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

# Permite execução direta via `python chatbot/main.py` resolvendo imports relativos.
if __package__ in (None, ""):
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    from chatbot.settings import settings  # type: ignore
    from chatbot.tools import APIClient, build_tools  # type: ignore
    from src.db_dao import RemoteLaboratoryDAO  # type: ignore
else:
    from .settings import settings
    from .tools import APIClient, build_tools
    from src.db_dao import RemoteLaboratoryDAO


def _resolve_openai_key(dao: RemoteLaboratoryDAO) -> Optional[str]:
    """
    Prefere chave manual salva no banco; caso não exista, tenta variável de ambiente.
    """
    try:
        settings_row = dao.get_ai_key_settings() or {}
        if settings_row.get("source") == "manual":
            manual_key, invalid = dao.load_manual_ai_key()
            if manual_key:
                return manual_key
            if invalid:
                print("Aviso: AI Key manual corrompida. Limparei o registro para permitir novo cadastro.")
                dao.clear_ai_key_settings()
    except Exception as exc:
        print(f"Aviso: não foi possível ler AI Key do banco: {exc}")
    env_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    return env_key


def build_agent(tools, api_key: str):
    llm = ChatOpenAI(model=settings.openai_model, temperature=0, api_key=api_key)
    return create_agent(
        llm,
        tools,
        system_prompt="Você é um assistente que conversa com o usuário e decide quando chamar as ferramentas disponíveis.",
    )


def _print_last_ai_message(messages: List[BaseMessage]) -> None:
    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last_ai is None:
        print("Sem resposta do modelo.")
        return
    content = last_ai.content
    if isinstance(content, (dict, list)):
        print(json.dumps(content, indent=2, ensure_ascii=False))
    else:
        print(content)


def _check_api_health(client: APIClient) -> bool:
    try:
        client.list_experiments()
        return True
    except httpx.HTTPError as exc:
        print(
            f"API indisponível em {client.base_url}. "
            "Garanta que o Flask esteja rodando e que o banco esteja acessível. "
            f"Detalhe: {exc}"
        )
        return False


def main() -> None:
    # Usa SQLite como padrão para o chatbot quando nada foi configurado.
    os.environ.setdefault("DB_BACKEND", "sqlite")
    dao = RemoteLaboratoryDAO()
    api_key = _resolve_openai_key(dao)
    if not api_key:
        raise RuntimeError(
            "Nenhuma AI Key encontrada. Cadastre na tela de Configurações ou defina OPENAI_API_KEY."
        )
    os.environ.setdefault("OPENAI_API_KEY", api_key)

    client = APIClient()
    if not _check_api_health(client):
        return
    tools = build_tools(client)
    agent = build_agent(tools, api_key)

    print("Chatbot conectado. Digite sua pergunta (Ctrl+C para sair).")
    messages: List[BaseMessage] = []
    while True:
        try:
            user_input = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando...")
            break
        if not user_input:
            continue
        try:
            messages.append(HumanMessage(content=user_input))
            result = agent.invoke({"messages": messages})
            messages = result["messages"]
            _print_last_ai_message(messages)
        except httpx.HTTPError as exc:
            print(
                f"API indisponível em {client.base_url}. "
                "Garanta que o Flask esteja rodando e que o banco esteja acessível. "
                f"Detalhe: {exc}"
            )
        except Exception as exc:
            print(f"Erro: {exc}")


if __name__ == "__main__":
    main()
