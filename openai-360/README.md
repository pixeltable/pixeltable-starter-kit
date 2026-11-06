# OpenAI 360: a warranty claims desk

A warranty claim arrives as a photo and a voice note. One application file (`app.py`) transcribes the note, screens
it, asks the Decisions API about the claim, drafts and speaks a reply for the claims it approves, and indexes every
transcript for search. Six OpenAI endpoints run in one table, and a seventh generates the demo inputs.

```bash
export OPENAI_API_KEY=sk-...        # before the first pxt command, else `uv run pxt daemon restart` after
cd openai-360
uv sync
uv run pxt schema update app.py claims
uv run python seed.py               # four generated demo claims
uv run pxt service update app.py claims
uv run pxt service list
```

## What runs on insert

| Column | Call | Result |
|--------|------|--------|
| `transcript` | `openai.transcriptions()` | The voice note as text |
| `flagged` | `openai.moderations()` | Whether the message needs a person first |
| `triage` | `openai.decisions()` | Four answers about the transcript and photo in one request |
| `damaged`, `consistent`, `cause`, `severity` | | The answers as columns: two probabilities, a choice, and a score from 0 (cosmetic) to 2 (unusable) |
| `route` | `route_claim()` | `approve` when the photo shows damage that matches the story, else `review` or `escalate` |
| `reply_text` | `openai.responses()` | A reply to the customer, for approved claims only |
| `voice_reply` | `openai.speech()` | The reply as audio |
| index on `transcript` | `openai.embeddings()` | `similar_claims()` finds earlier claims like this one |

`reply_prompt()` returns `None` unless `route` is `approve`. A `None` argument skips the call, so a claim sent to review
never reaches `responses()` or `speech()`, and its `reply_text` and `voice_reply` stay empty.

`seed.py` inserts four rows into `demo_inputs`, whose `photo` comes from `openai.image_generations()` and whose
`voice_note` comes from `openai.speech()`, then files them as claims. The demo inputs are synthetic. The smartphone
and the headphones are approved. The laptop's photo shows no damage and the coffee maker's fault is not visible, so
both go to review:

```text
               product    route  damaged  consistent
0               laptop   review     0.00        0.00
1           smartphone  approve     1.00        0.95
2  wireless headphones  approve     1.00        0.96
3         coffee maker   review     0.04        0.51
```

## Look inside

```bash
uv run pxt describe claims/claims           # every column and the call that computes it
uv run pxt computed claims/claims           # just the computed columns
uv run pxt rows claims/claims               # the first rows
uv run pxt errors claims/claims             # rows where a call failed
uv run pxt history claims/claims            # one version per insert or schema change
uv run pxt dashboard                        # Lineage tab: each table's columns and the call behind each
```

From Python, bind the models and query the table:

```python
import app

app.TableModel.bind_all("claims")
C = app.Claims
C.where(C.route == "approve").select(C.product, C.cause, C.reply_text).collect()
```

To change the gate, edit `route_claim()`, then rerun it on the stored claims. `reply`, `reply_text` and
`voice_reply` rerun with it, for every row: a claim that becomes approved gets a reply, one that stops being approved
loses it, and claims that stay approved get a fresh reply, at the cost of a new `responses()` and `speech()` call each.

```bash
uv run pxt recompute claims/claims route -f
```

## HTTP

`pxt service list` prints the port and each route's inputs and outputs. `/api/similar` and `/api/review` serve
`similar_claims()` and `review_queue()`.

```bash
curl -s -X POST http://127.0.0.1:<port>/api/claims \
  -F "photo=@/path/to/photo.jpg" \
  -F "voice_note=@/path/to/note.mp3" \
  -F "product=blender"

curl -s http://127.0.0.1:<port>/api/review

curl -s -X POST http://127.0.0.1:<port>/api/similar \
  -H "Content-Type: application/json" \
  -d '{"text": "the screen cracked when I dropped it", "limit": 3}'
```

## Same file, hosted

```bash
uv run pxt db update pxt://org:mydb
uv run pxt secret set pxt://org OPENAI_API_KEY=sk-...
uv run pxt db restart pxt://org:mydb
uv run pxt schema update app.py pxt://org:mydb
uv run pxt service update app.py pxt://org:mydb
```

[Cloud docs](https://docs.pixeltable.com/howto/deployment/cloud).

## Container

`OPENAI_API_KEY=sk-... docker compose up --build` serves on port 8000.

| Object | Role |
|--------|------|
| `claims.claims` | Claims: transcript, moderation, decisions, route, reply, voice reply, transcript index |
| `claims.demo_inputs` | Generated demo photos and voice notes |
| `similar_claims` | Transcript similarity search |
| `review_queue` | Claims not approved, most severe first |
