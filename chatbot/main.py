from __future__ import annotations

import json
import os
from typing import List

import httpx
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from .settings import settings
from .tools import APIClient, build_tools


def build_agent(tools):
    llm = ChatOpenAI(model=settings.openai_model, temperature=0)
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
    api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        raise RuntimeError("Defina a variável de ambiente OPENAI_API_KEY antes de rodar o chatbot.")
    os.environ.setdefault("OPENAI_API_KEY", api_key)

    client = APIClient()
    if not _check_api_health(client):
        return
    tools = build_tools(client)
    agent = build_agent(tools)

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
