# Get Started

This guide explains how to run and test the Semantic Query Agent on Windows.

## What you need

Before starting, install:

- [Python 3.13](https://www.python.org/downloads/)
- Visual Studio Code, if you want to view or run the notebook
- An Abacus.AI RouteLLM API key

Use standard CPython 3.13. Do not use Python 3.14 free-threaded builds because some Gradio dependencies do not yet support them.

## 1. Open the project

Open the `semantic-query-agent` folder in Visual Studio Code. Then open a PowerShell terminal in that folder.

## 2. Create a virtual environment

Run these commands one at a time:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell says that script execution is disabled, run this command once, then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

When the environment is active, your terminal line starts with `(.venv)`.

## 3. Install the project packages

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

Wait for the installation to finish without errors.

## 4. Add your RouteLLM key

Create your local environment file from the template:

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code. Replace this value:

```text
ABACUS_API_KEY=your_route_llm_api_key
```

with your real Abacus.AI RouteLLM API key, then save the file.

Do not share or commit `.env`. It is already excluded by `.gitignore`.

## 5. Start the app

```powershell
py app.py
```

After the terminal reports a local URL, open this address in a browser:

```text
http://127.0.0.1:7860
```

Keep the PowerShell window open while using the app. To stop the app, return to the terminal and press `Ctrl+C`.

## 6. Test the agent

In the browser:

1. Choose a question in **Demo questions**, or enter your own business question.
2. Select **Run query**.
3. Confirm that the chat contains a business-language answer.
4. Open **Generated SQL** and confirm it contains a read-only `SELECT` or `WITH` query.
5. Open **Schema context used** to see the tables and columns the agent selected.
6. Open the **DataFrame results** tab to view the query results.

Try these questions:

```text
Which customers placed the most orders?
Show the top 10 products by revenue.
Which products are low in stock?
```

## 7. Test the local project files

Stop the app first with `Ctrl+C`, then run:

```powershell
py -m py_compile app.py
py -c "import json, pathlib; notebook = json.loads(pathlib.Path('agent1.ipynb').read_text(encoding='utf-8')); [compile(''.join(cell['source']), f'cell-{index}', 'exec') for index, cell in enumerate(notebook['cells']) if cell['cell_type'] == 'code']; print('Notebook code is valid')"
py -c "import sqlite3; connection = sqlite3.connect('file:data/northwind.db?mode=ro', uri=True); print(connection.execute('SELECT COUNT(*) FROM Customers').fetchone()[0], 'customers found')"
```

Each command should finish without an error. The last command should report `93 customers found`.

## Optional: Use the notebook

All LLM code is in `agent1.ipynb`.

1. Open `agent1.ipynb` in VS Code.
2. Select the Python interpreter from `.venv` when VS Code asks for a kernel.
3. Run the notebook cells from top to bottom.
4. You can call `answer_question("Show sales by product category.")` in a new code cell to test the agent directly.

The Gradio app loads the notebook code automatically when you submit your first question.
