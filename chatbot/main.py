from __future__ import annotations

import json
import os

from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI

from .settings import settings
from .tools import APIClient, build_tools


def main() -> None:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

    llm = ChatOpenAI(model=settings.openai_model, temperature=0)
    client = APIClient()
    tools = build_tools(client)

    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
    )

    print("Chatbot conectado. Digite sua pergunta (Ctrl+C para sair).")
    while True:
        try:
            user_input = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando...")
            break
        if not user_input:
            continue
        try:
            response = agent.run(user_input)
            if isinstance(response, (dict, list)):
                print(json.dumps(response, indent=2, ensure_ascii=False))
            else:
                print(response)
        except Exception as exc:
            print(f"Erro: {exc}")


if __name__ == "__main__":
    main()
