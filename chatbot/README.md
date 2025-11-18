# Chatbot para Gerenciar Experimentos

Este diretório contém um protótipo de agente conversacional que utiliza LangChain + OpenAI para interagir com os endpoints REST expostos pelo `lab-manager/plant_config_app.py`.

## Requisitos

- Python 3.9+
- Servidor Flask rodando localmente (`python lab-manager/plant_config_app.py`)
- Variáveis de ambiente:
  - `OPENAI_API_KEY` (ou o equivalente para o provedor escolhido)
  - Opcional: `CHATBOT_API_BASE` para apontar para outro host (padrão: `http://localhost:5000/api`)

Instale dependências:

```bash
pip install -r chatbot/requirements.txt
```

## Uso

1. Inicie o Flask/API.
2. Execute o chatbot:
   ```bash
   python -m chatbot.main
   ```
3. Digite perguntas como "Liste os experimentos" ou "Crie um experimento chamado ..." e observe como o agente faz chamadas às ferramentas `list_experiments`, `create_experiment`, etc.

## Estrutura

- `main.py` – script principal que configura o LLM e as ferramentas.
- `tools.py` – wrappers HTTP para os endpoints `/api/experiments` e `/api/ground-truth`.
- `settings.py` – leitura de variáveis de ambiente e configuração do cliente.
- `requirements.txt` – dependências necessárias.

A proposta é ser simples; ajuste conforme evoluir (ex.: adicionar logging, UI web, autenticação nos endpoints, etc.).
