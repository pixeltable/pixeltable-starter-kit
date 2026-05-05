# Pixeltable Serving & Deployment: Developer Journey

This document outlines the end-to-end experience for developers (e.g., **Ed** and **Sarah**) moving from local Pixeltable prototyping to team collaboration and production deployment using the `pxt serve` and `pxt deploy` ecosystem.

---

## 1. Local Development (Schema-as-Code)

**Ed** starts by defining his multimodal pipeline in a Python script. In Pixeltable, the **code is the source of truth** for the schema.

```python
# setup_pixeltable.py
import pixeltable as pxt
from pixeltable.functions.openai import chat_completions

pxt.create_dir('prod_app', if_exists='ignore')
t = pxt.create_table('prod_app.queries', {'prompt': pxt.String})

# Add an AI-powered computed column
t.add_computed_column(
    answer=chat_completions(
        messages=[{'role': 'user', 'content': t.prompt}],
        model='gpt-4o'
    )
)
```

---

## 2. Local Testing (`pxt serve`)

Ed wants to test his schema as an API. He has two paths depending on his needs.

### Path A: Zero-Boilerplate CLI (Best for Teams)
Ed creates a `service.toml` file. This declarative file is the best practice for team collaboration as it can be versioned in Git.

```toml
# service.toml
[[service]]
name = "my-agent"
port = 8000

[[service.routes]]
type = "insert"
table = "prod_app.queries"
path = "/ask"
inputs = ["prompt"]
outputs = ["prompt", "answer"]
```

Ed runs the service:
```bash
pxt serve my-agent --config service.toml
```

Or for a quick one-off without a TOML file:
```bash
pxt serve insert --table prod_app.queries --path /ask \
  --inputs prompt --outputs prompt answer --port 8000
```

### Path B: Existing FastAPI App
If Ed already has a FastAPI application, he integrates Pixeltable using the `FastAPIRouter`.

```python
# main.py
import fastapi
import uvicorn
import pixeltable as pxt
from pixeltable.serving import FastAPIRouter

t = pxt.get_table('prod_app.queries')

app = fastapi.FastAPI()
router = FastAPIRouter()
router.add_insert_route(t, path="/ask", inputs=["prompt"], outputs=["prompt", "answer"])
app.include_router(router)

uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 3. Production Deployment (`pxt deploy`)

When Ed is ready for production, he promotes his local environment to the Pixeltable Cloud.

### The Deployment Config (`pixeltable.toml`)
Ed moves his environment settings into a config file to ensure reproducibility.

```toml
# pixeltable.toml
[project]
name = "video-rag-agent"
organization = "acme-corp"

[deployment]
service_config = "service.toml"  # Points to his API definition

[environment]
requirements = "requirements.txt"

[resources]
tier = "paid"
workers = 2
cpu = 2
memory = "4GB"
```

### Executing the Deploy
```bash
pxt deploy
```
**The Cloud Experience:**
1. **Build:** Pixeltable builds a Docker image containing Ed's code and dependencies.
2. **Registry:** The image is versioned and stored in a private ECR.
3. **Provision:** Northflank provisions worker nodes based on the `resources` spec.
4. **Live:** The endpoint becomes available at `https://pxt.run/acme-corp/main/ask`.
5. **Auth:** Ed receives a **Runtime API Key** (`pxt_live_...`) for his production app.

---

## 4. Team Collaboration (The Git Flow)

Ed pushes his project to GitHub:
```bash
git add setup_pixeltable.py service.toml pixeltable.toml requirements.txt
git commit -m "Initial agent deploy"
git push
```

### Sarah Joins the Project
**Sarah** clones the repo. Her local Pixeltable environment is initially empty.

1. **Initialize Local Sandbox:**
   Sarah runs Ed's setup script to mirror the schema in her local `PIXELTABLE_HOME`.
   ```bash
   python setup_pixeltable.py
   ```

2. **Iterate:**
   Sarah adds a `summary` column to `setup_pixeltable.py`. She tests it locally using `pxt serve`.

3. **Re-deploy:**
   Sarah pushes her code changes to Git and runs:
   ```bash
   pxt deploy
   ```
   Pixeltable Cloud performs a **Rolling Deploy**, updating the live endpoint to Version 2 without downtime.

---

## 5. Architectural Summary

| Feature | Local (`pxt serve`) | Cloud (`pxt deploy`) |
|---------|--------------------|----------------------|
| **Auth** | None (Localhost) | **Runtime Key** (Bearer Token) |
| **Storage** | Local `PIXELTABLE_HOME` | Ephemeral Workers + Persistent SQL Export |
| **Scaling** | Single Process | Managed Cluster (Northflank) |
| **Observability** | Console Logs | Dashboard (Per-cell errors, Usage, Logs) |

### Best Practices for Teams:
1. **Code is Truth:** Always define schemas in Python scripts, never via ad-hoc CLI commands in production.
2. **Version Everything:** Keep `service.toml` and `pixeltable.toml` in Git.
3. **Dual-Key Safety:** Use **User Keys** for deployment and **Runtime Keys** for application access.
