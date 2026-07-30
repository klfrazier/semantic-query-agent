from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any

import gradio as gr
import nbformat
import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
NOTEBOOK_PATH = ROOT_DIR / "agent1.ipynb"
DATABASE_PATH = ROOT_DIR / "data" / "northwind.db"
_AGENT_LOCK = Lock()
_AGENT_NAMESPACE: dict[str, Any] | None = None

EXAMPLES = [
    "Which customers placed the most orders?",
    "Show the top 10 products by revenue.",
    "What were monthly sales totals in 1997?",
    "Which products are low in stock?",
    "List orders that were shipped late.",
    "Which employees generated the most sales?",
    "Show sales by product category.",
    "Which countries have the most customers?",
]


def load_agent() -> dict[str, Any]:
    global _AGENT_NAMESPACE
    with _AGENT_LOCK:
        if _AGENT_NAMESPACE is None:
            load_dotenv(ROOT_DIR / ".env")
            namespace: dict[str, Any] = {"__name__": "semantic_query_agent_notebook"}
            notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
            for cell in notebook.cells:
                if cell.cell_type == "code":
                    exec(cell.source, namespace)
            _AGENT_NAMESPACE = namespace
    return _AGENT_NAMESPACE


def run_query(message: str, history: list[dict[str, str]] | None) -> tuple[list[dict[str, str]], str, str, str, str, pd.DataFrame]:
    if not message or not message.strip():
        return history or [], "", "", "", "", pd.DataFrame()

    started = time.perf_counter()
    try:
        agent = load_agent()
        answer = agent["answer_question"](message.strip())
        response = answer["response"]
        sql = answer["sql"]
        schema = answer["schema_context"]
        dataframe = answer["dataframe"]
        execution = f"{round((time.perf_counter() - started) * 1000, 1)} ms total · {answer['execution_ms']:.1f} ms SQLite"
    except Exception as error:
        response = f"I could not complete that request: {error}"
        sql = ""
        schema = ""
        dataframe = pd.DataFrame()
        execution = f"{round((time.perf_counter() - started) * 1000, 1)} ms total"

    messages = list(history or []) + [{"role": "user", "content": message}, {"role": "assistant", "content": response}]
    return messages, "", sql, schema, execution, dataframe


def inspect_database() -> str:
    with sqlite3.connect(DATABASE_PATH) as connection:
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name", connection)["name"].tolist()
    return json.dumps({"database": str(DATABASE_PATH.relative_to(ROOT_DIR)), "tables": tables}, indent=2)


with gr.Blocks(title="Semantic Query Agent") as demo:
    gr.Markdown("# Semantic Query Agent\nAsk business questions about the local Microsoft Northwind SQLite database.")
    with gr.Row():
        with gr.Column(scale=3):
            chat = gr.Chatbot(label="Business conversation", height=480)
            question = gr.Textbox(label="Ask a question", placeholder="Which products generated the most revenue?", lines=2)
            with gr.Row():
                submit = gr.Button("Run query", variant="primary")
                clear = gr.Button("Clear")
            gr.Examples(EXAMPLES, inputs=question, label="Demo questions")
        with gr.Column(scale=2):
            with gr.Accordion("Generated SQL", open=True):
                sql_view = gr.Code(language="sql", label="Read-only SQL")
            with gr.Accordion("Schema context used", open=False):
                schema_view = gr.Code(language=None, label="Relevant tables and columns")
            execution_view = gr.Textbox(label="Execution time", interactive=False)
            gr.Code(value=inspect_database(), language="json", label="Local database")
    with gr.Tab("DataFrame results"):
        results = gr.Dataframe(label="Query results", interactive=False)

    outputs = [chat, question, sql_view, schema_view, execution_view, results]
    submit.click(run_query, inputs=[question, chat], outputs=outputs)
    question.submit(run_query, inputs=[question, chat], outputs=outputs)
    clear.click(lambda: ([], "", "", "", "", pd.DataFrame()), outputs=outputs)


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
