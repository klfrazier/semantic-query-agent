# Semantic Query Agent

A local Gradio demo that turns natural-language business questions into read-only SQLite queries against the Microsoft Northwind database. LLM calls use the OpenAI Agents SDK via Abacus.AI RouteLLM; the UI and database run locally.

## Requirements

- CPython 3.13 (recommended; current Gradio dependencies do not yet support Python 3.14 free-threaded builds)
- An Abacus.AI RouteLLM API key

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `ABACUS_API_KEY` in `.env`, then launch:

```powershell
py app.py
```

Open <http://127.0.0.1:7860>. The app presents a chat interface, generated SQL, schema context, execution time, and interactive DataFrame results. It includes eight demonstration questions.

## Notebook workflow

All LLM and agent logic is in [agent1.ipynb](agent1.ipynb). `app.py` executes the notebook code cells in-process, so the application has no separate LLM runtime module. You can open and run the notebook in VS Code or JupyterLab.

## Safety

The app opens `data/northwind.db` in SQLite read-only mode. It accepts only a single `SELECT` or `WITH` statement and rejects mutating SQLite keywords before execution.

## Project layout

```text
agent1.ipynb       Agent and LLM logic
app.py             Local Gradio application
data/northwind.db  Microsoft Northwind SQLite database
.env.example       RouteLLM configuration template
```
