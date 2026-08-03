# semantic-query_agent-spec.md

# 🤖 Agent Specification & Design — Semantic Query Agent

## 1. System Overview & Objective
* **Agent Name**: `Semantic Query Agent`
* **Primary Persona**: `Business Intelligence Analyst — translates plain-English business questions into safe, read-only SQL and explains the results in non-technical language`
* **Target Workload**: `Accepts a natural-language business question, generates exactly one read-only SQLite SELECT or WITH query against the Microsoft Northwind database, executes it, and returns a business-language explanation alongside the raw result set and the generated SQL for inspection.`
* **Core Metrics (KPIs)**:
  - SQL correctness rate against the eight canonical demo questions: 100 %
  - End-to-end latency (LLM + SQLite): < 5 000 ms on a local machine
  - Safety: 0 mutating statements reaching SQLite execution
  - Structured-output parse failures: < 1 % of requests

---

## 2. Core Architecture ("The Brain")
* **Primary LLM**: `Abacus.AI RouteLLM (route-llm) via OpenAI-compatible endpoint https://routellm.abacus.ai/v1`
* **Fallback LLM**: `None currently configured — the ABACUS_MODEL env var can be changed to any RouteLLM-supported model for manual failover`
* **System Prompt Template**:
```text
You are Semantic Query Agent. Translate a business question into one safe
SQLite query for Microsoft Northwind. Return structured output.
Generate exactly one read-only SELECT or WITH query.
Never generate INSERT, UPDATE, DELETE, DROP, ALTER, ATTACH, DETACH,
PRAGMA, or multiple statements.
Quote Northwind identifiers containing spaces, including "Order Details".
Use only this schema:

{SCHEMA_CONTEXT}
```
* **Design Pattern**: `Prompt Chaining — single-shot LLM call returns a structured SQLPlan (sql, explanation, schema_context); a deterministic validation + execution layer then runs the SQL and assembles the final response. No autonomous loop or multi-agent orchestration.`

---

## 3. Data Flow & Input/Output Contracts

### Input Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "question": {
      "type": "string",
      "description": "Natural-language business question submitted by the user"
    }
  },
  "required": ["question"]
}
```

> The Gradio UI passes `question` as a plain string to `answer_question(question)`.
> Chat history is displayed in the UI but is **not** forwarded to the LLM — each call is stateless.

### Intermediate Structured Output — SQLPlan (Pydantic)
```json
{
  "type": "object",
  "properties": {
    "sql": {
      "type": "string",
      "description": "One read-only SQLite SELECT or WITH query"
    },
    "explanation": {
      "type": "string",
      "description": "Short business-language explanation of what the query answers"
    },
    "schema_context": {
      "type": "string",
      "description": "Relevant tables and columns used to build the query"
    }
  },
  "required": ["sql", "explanation", "schema_context"]
}
```

### Final Output Schema — answer_question() return value
```json
{
  "type": "object",
  "properties": {
    "response":       { "type": "string",  "description": "Business explanation + row count summary" },
    "sql":            { "type": "string",  "description": "Validated, executed SQLite query" },
    "schema_context": { "type": "string",  "description": "Tables and columns the LLM selected" },
    "execution_ms":   { "type": "number",  "description": "SQLite query execution time in milliseconds" },
    "dataframe":      { "type": "object",  "description": "pandas DataFrame containing query results" }
  },
  "required": ["response", "sql", "schema_context", "execution_ms", "dataframe"]
}
```

---

## 4. Operational Boundaries & Guardrails
A **two-tier boundary system** enforces safety without a human-in-the-loop for read-only queries.

### ✅ Always Do (Autonomous Actions)
* Generate exactly one `SELECT` or `WITH` statement per user question.
* Validate the LLM output against the `SQLPlan` Pydantic model before any execution.
* Open `northwind.db` exclusively in SQLite URI read-only mode (`?mode=ro`) for every query.
* Return a business-language row-count summary alongside the SQL and DataFrame.
* Surface execution latency (total ms and SQLite-only ms) to the user on every request.
* Quote space-containing Northwind identifiers (e.g., `"Order Details"`) in generated SQL.

### ❌ Never Do (Hard Stops)
* Never execute a query that does not begin with `SELECT` or `WITH` after stripping whitespace.
* Never execute a query containing a semicolon (multi-statement prevention) or any of the forbidden keywords: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `REINDEX`, `CREATE`, `REPLACE`.
* Never open `northwind.db` outside of read-only URI mode.
* Never forward raw internal exception tracebacks to the Gradio chat — surface a sanitized error message only.
* Never pass conversation history to the LLM (no session memory; each question is fully independent).

> **Enforcement mechanism**: `validate_sql()` in `agent1.ipynb` (cell 4) applies a compiled regex blocklist and prefix check before `pd.read_sql_query()` is called. A `ValueError` here aborts execution and returns a sanitized error to the UI.

---

## 5. Memory & Context Management
* **Short-Term Memory**: `None — each call to answer_question() is fully stateless. The Gradio chatbot widget accumulates display history client-side, but this history is never sent to the LLM.`
* **Long-Term Memory**: `None — no vector store, no session database, no persistent state between restarts.`
* **Schema Context**: `The full Northwind DDL is loaded once at agent startup (database_schema() in cell 3) and injected into every system prompt. This is a fixed, ~2 KB static string — not dynamic retrieval.`
* **Context Eviction Policy**: `Not applicable — the only context is the static schema + the single user question. No windowing or summarization is needed.`

---

## 6. Tooling & MCP Integration
The agent uses no external MCP servers or tool calls. All logic is contained in two local modules:

| Tool Name | Function / Interface | Description | Timeout |
| :--- | :--- | :--- | :--- |
| `LLM Structured Call` | `Runner.run_sync(agent, question)` | Sends question + schema system prompt to RouteLLM; returns a `SQLPlan` Pydantic object | Governed by `openai-agents` SDK default (network-dependent) |
| `SQL Validator` | `validate_sql(sql: str) -> str` | Regex + prefix check; raises `ValueError` on any forbidden pattern | < 1 ms (pure Python) |
| `SQLite Executor` | `pd.read_sql_query(sql, connection)` | Executes validated query against `northwind.db` in read-only mode; returns a DataFrame | Typically < 50 ms locally |
| `Schema Loader` | `database_schema() -> str` | Reads DDL for all non-system tables from `sqlite_master` at startup | One-time; < 10 ms |
| `Database Inspector` | `inspect_database() -> str` | Returns JSON list of table names; used by Gradio UI info panel only | < 5 ms |

---

## 7. Orchestration & Implementation Stack
* **Agentic Framework**: `OpenAI Agents SDK (openai-agents) — single-agent, single-turn, structured output mode`
* **LLM Gateway**: `Abacus.AI RouteLLM — OpenAI-compatible REST API at https://routellm.abacus.ai/v1; model name configurable via ABACUS_MODEL env var (default: route-llm)`
* **UI Layer**: `Gradio 5.x (gr.Blocks) — local web UI on 127.0.0.1:7860; components: Chatbot, Code (SQL), Code (schema), Textbox (latency), Dataframe, Accordion, Examples`
* **Agent Logic Location**: `agent1.ipynb — executed in-process by app.py via nbformat.read() + exec(); no separate service or subprocess`
* **Database**: `SQLite 3 — Microsoft Northwind, local file at data/northwind.db, opened read-only via URI`
* **Infrastructure**: `Local Python 3.13 process — no containers, no cloud deployment, no message queue`
* **Configuration**: `.env file — ABACUS_API_KEY, ABACUS_BASE_URL, ABACUS_MODEL; loaded via python-dotenv`
* **Observability / Tracing**: `set_tracing_disabled(True) — OpenAI Agents SDK tracing is explicitly disabled. Latency is surfaced in the UI (total ms + SQLite ms). No external tracing platform is connected.`
* **Concurrency**: `Threading lock (_AGENT_LOCK) protects the shared _AGENT_NAMESPACE singleton so the notebook is executed only once across concurrent Gradio requests`

---

## 8. Test Plan & Acceptance Criteria

### Golden Dataset — Eight Canonical Demo Questions
Each question must produce a valid `SELECT`/`WITH` query, a non-empty DataFrame, and a coherent business explanation.

| # | Question | Expected SQL pattern | Expected result shape |
|---|---|---|---|
| 1 | Which customers placed the most orders? | `GROUP BY CustomerID … ORDER BY … DESC` | Customer name + order count, descending |
| 2 | Show the top 10 products by revenue. | `SUM(UnitPrice * Quantity) … LIMIT 10` | Product name + total revenue, top 10 |
| 3 | What were monthly sales totals in 1997? | `strftime('%Y-%m', OrderDate) … WHERE … 1997` | Month + sales total, 12 rows |
| 4 | Which products are low in stock? | `WHERE UnitsInStock < [threshold]` | Product name + units in stock |
| 5 | List orders that were shipped late. | `WHERE ShippedDate > RequiredDate` | Order ID + dates |
| 6 | Which employees generated the most sales? | `JOIN … GROUP BY EmployeeID … ORDER BY … DESC` | Employee name + sales total |
| 7 | Show sales by product category. | `JOIN Categories … GROUP BY CategoryName` | Category name + total sales |
| 8 | Which countries have the most customers? | `GROUP BY Country … ORDER BY … DESC` | Country + customer count |

### Edge Case Handling
| Scenario | Expected Behavior |
|---|---|
| LLM returns a non-SQLPlan output | `RuntimeError` caught in `run_query()`; UI shows sanitized message, no traceback |
| LLM generates a mutating statement | `validate_sql()` raises `ValueError`; query never reaches SQLite |
| LLM embeds a second statement (semicolon) | `validate_sql()` rejects on `;` presence |
| SQLite query returns 0 rows | DataFrame is empty; response says "Returned 0 rows" — not an error |
| `ABACUS_API_KEY` missing | `RuntimeError` raised at notebook exec time; app fails to start with a clear message |
| Network timeout to RouteLLM | Exception propagated; UI shows sanitized error message |
| Question is blank or whitespace | `run_query()` returns early with no LLM call; UI state unchanged |

### Max Execution Limits
* **LLM call**: No hard timeout configured — relies on RouteLLM server timeout. Recommended future addition: 30-second client-side timeout.
* **SQLite query**: No explicit timeout — acceptable given read-only, local, small database. All demo queries complete in < 50 ms.
* **Total end-to-end**: Target < 5 000 ms; displayed to user on every request via the execution time textbox.
* **Loop iterations**: Not applicable — the design pattern is single-shot prompt chaining with no autonomous loop.
