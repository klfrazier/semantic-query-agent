# Semantic Query Agent — Process & Data Flow

```mermaid
flowchart TD
    A([User types question\nand clicks Run Query]) --> B{Input blank?}
    B -- Yes --> B1([Return early\nno LLM call])
    B -- No --> C{Agent loaded?}

    subgraph STARTUP ["Stage 2 · Agent Lazy-Load (first call only)"]
        C -- No --> D[Acquire _AGENT_LOCK\nthread-safe singleton]
        D --> E[load_dotenv\nABACUS_API_KEY · BASE_URL · MODEL]
        E --> F[nbformat.read agent1.ipynb\nparse notebook JSON]
        F --> G[exec each code cell\ninto _AGENT_NAMESPACE]
        G --> G1[Cell 2: AsyncOpenAI client\nnormalize_usage patch\nset_default_openai_client]
        G --> G2[Cell 3: database_schema\nreads Northwind DDL\nbuilds SCHEMA_CONTEXT string\nSQLPlan Pydantic model\nSYSTEM_PROMPT assembled\nAgent object created]
        G --> G3[Cell 4: validate_sql\nand answer_question defined]
    end

    C -- Yes --> H
    G3 --> H

    subgraph LLM ["Stage 4 · LLM Call via Abacus.AI RouteLLM"]
        H[answer_question called\nwith stripped question] --> I[Runner.run_sync\nOpenAI Agents SDK]
        I --> J[HTTP POST\nroutellm.abacus.ai/v1/chat/completions]
        J --> K[System prompt:\nfull Northwind DDL schema\nUser: question\nResponse format: SQLPlan JSON]
        K --> L[LLM Response\nSQLPlan object\nsql · explanation · schema_context]
    end

    subgraph VALIDATE ["Stage 5 · SQL Validation"]
        L --> M{validate_sql}
        M --> M1[Strip whitespace\nremove trailing semicolons]
        M1 --> M2{Starts with\nSELECT or WITH?}
        M2 -- No --> ERR
        M2 -- Yes --> M3{Contains\nsemicolon?}
        M3 -- Yes --> ERR
        M3 -- No --> M4{Matches FORBIDDEN\nregex blocklist?\nINSERT · UPDATE · DELETE\nDROP · ALTER · PRAGMA · etc.}
        M4 -- Yes --> ERR
        M4 -- No --> N[SQL validated ✓]
        ERR([ValueError raised\ncaught in run_query\nsanitized error shown\nall outputs cleared]) 
    end

    subgraph DB ["Stage 6 · SQLite Execution"]
        N --> O[sqlite3.connect\nfile:data/northwind.db?mode=ro\nread-only URI mode]
        O --> P[pd.read_sql_query\nexecute validated SQL]
        P --> Q[pandas DataFrame returned\nexecution_ms recorded]
    end

    subgraph ASSEMBLE ["Stage 7–8 · Result Assembly & Metrics"]
        Q --> R[answer_question returns dict\nsql · response · schema_context\nexecution_ms · dataframe]
        R --> S[run_query calculates metrics\ntotal ms via perf_counter\nnum_tables via regex on FROM/JOIN\nnum_rows via len dataframe]
        S --> T[Assemble 9-tuple output\nmessages · cleared input · sql\nschema · execution · num_tables\nnum_rows · dataframe · tab selection]
    end

    subgraph UI ["Stage 9 · Gradio UI Rendering"]
        T --> U1[gr.Chatbot\nFull conversation history\nnew answer appended]
        T --> U2[gr.Textbox\nQuestion input cleared]
        T --> U3[gr.Code — SQL\nGenerated SQL\nsyntax-highlighted]
        T --> U4[gr.Code — Schema\nTables & columns\nLLM selected]
        T --> U5[gr.Textbox\nX ms total · Y ms SQLite]
        T --> U6[gr.Textbox\nTable count]
        T --> U7[gr.Textbox\nRow count returned]
        T --> U8[gr.Dataframe\nInteractive data table]
        T --> U9[gr.Tabs\nForced to Generated SQL tab]
    end

    style STARTUP fill:#e8f4fd,stroke:#2196F3
    style LLM fill:#fff8e1,stroke:#FF9800
    style VALIDATE fill:#fce4ec,stroke:#E91E63
    style DB fill:#e8f5e9,stroke:#4CAF50
    style ASSEMBLE fill:#f3e5f5,stroke:#9C27B0
    style UI fill:#e0f2f1,stroke:#009688
```

---

## Stage Summary

| # | Stage | Owner | Key Output |
|---|---|---|---|
| 1 | Button click / Enter key fires `run_query()` | `app.py` | Function call initiated |
| 2 | Agent lazy-load — notebook exec'd once | `app.py` + `agent1.ipynb` | `_AGENT_NAMESPACE` populated, `Agent` object ready |
| 3 | `answer_question(question)` called | `agent1.ipynb` Cell 4 | Async agent runner invoked |
| 4 | LLM call → RouteLLM API | `agent1.ipynb` Cell 4 | `SQLPlan` (sql, explanation, schema_context) |
| 5 | SQL validation — blocklist + structure checks | `agent1.ipynb` Cell 4 | Validated SQL string or `ValueError` |
| 6 | SQLite execution in read-only mode | `agent1.ipynb` Cell 4 | `pandas.DataFrame` + `execution_ms` |
| 7 | Result dict assembled | `agent1.ipynb` Cell 4 | Dict with all result fields |
| 8 | Metrics calculated, 9-tuple built | `app.py` | Gradio output tuple |
| 9 | UI components updated | Gradio / `app.py` | Chatbot, SQL tab, dataframe, metrics all rendered |

## Key Design Notes

- **No conversation history to LLM** — chat history renders in the Gradio Chatbot widget but every LLM call is stateless (question only).
- **Schema is static** — Northwind DDL is read once at startup and injected into every system prompt; no vector search or dynamic retrieval.
- **Two-tier SQL safety** — LLM instructed via prompt (Tier 1) + hard regex blocklist and read-only SQLite URI (Tier 2).
- **Thread safety** — `_AGENT_LOCK` ensures the notebook is exec'd exactly once even under concurrent Gradio requests.
- **Error boundary** — any exception in stages 3–7 is caught; a sanitized message appears in chat and all other outputs are reset.
