"""pxt schema update app.py claims && pxt service update app.py claims"""

# ruff: noqa: F821

import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions import openai
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()

MODEL = "gpt-6-luna"
QUESTIONS = [
    {"type": "predicate", "name": "damaged", "instructions": "Does the photo show physical damage to the product?"},
    {
        "type": "predicate",
        "name": "consistent",
        "instructions": "Does the photo match what the customer says happened?",
    },
    {
        "type": "choice",
        "name": "cause",
        "instructions": "What most likely caused the problem?",
        "choices": [
            {"value": "accident"},
            {"value": "manufacturing defect"},
            {"value": "wear and tear"},
            {"value": "unclear"},
        ],
    },
    {
        "type": "score",
        "name": "severity",
        "instructions": "How badly is the product affected?",
        "levels": [{"label": "cosmetic"}, {"label": "partly working"}, {"label": "unusable"}],
    },
]


@pxt.udf
def route_claim(damaged: float | None, consistent: float | None, flagged: bool | None) -> str:
    if flagged:
        return "escalate"
    if damaged is not None and consistent is not None and damaged >= 0.7 and consistent >= 0.7:
        return "approve"
    return "review"


@pxt.udf
def reply_prompt(product: str, transcript: str, route: str) -> list | None:
    if route != "approve":
        return None  # a null input skips responses() and speech()
    return [
        {
            "role": "user",
            "content": (
                f"You handle warranty claims. In two warm sentences, tell the customer that their {product} "
                f"replacement is approved and ships within 3 days. Write only those two sentences: no greeting, "
                f"signature or placeholders. Their message: {transcript}"
            ),
        }
    ]


class DemoInputs(TableModel, name="demo_inputs"):
    product: pxt.String
    photo_prompt: pxt.String
    story: pxt.String
    photo = openai.image_generations(
        photo_prompt, model="gpt-image-2", model_kwargs={"quality": "low", "size": "1024x1024"}
    ).data[0]
    voice_note = openai.speech(story, model="gpt-4o-mini-tts", voice="coral")


class Claims(TableModel, name="claims"):
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    product: pxt.String
    photo: pxt.Image
    voice_note: pxt.Audio
    transcript = openai.transcriptions(voice_note, model="gpt-4o-transcribe").text.astype(pxt.String | None)
    flagged = openai.moderations(transcript).results[0].flagged
    triage = openai.decisions(
        [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Product: " + product + ". Customer: " + transcript},
                    {"type": "input_image", "image_url": photo},
                ],
            }
        ],
        questions=QUESTIONS,
        model=MODEL,
    )
    damaged = triage.answers[0].probability
    consistent = triage.answers[1].probability
    cause = triage.answers[2].choice
    severity = triage.answers[3].score
    route = route_claim(damaged, consistent, flagged)
    reply = openai.responses(reply_prompt(product, transcript, route), model="gpt-4o-mini")
    reply_text = reply.output[0].content[0].text.astype(pxt.String | None)
    voice_reply = openai.speech(reply_text, model="gpt-4o-mini-tts", voice="alloy")
    __indexes__ = [pxt.EmbeddingIndex(transcript, embedding=openai.embeddings.using(model="text-embedding-3-small"))]


@pxt.query
def similar_claims(text: str, limit: int = 5) -> pxt.Query:
    sim = Claims.transcript.similarity(string=text)
    return (
        Claims.order_by(sim, asc=False)
        .select(Claims.id, Claims.product, Claims.cause, Claims.route, Claims.transcript, score=sim)
        .limit(limit)
    )


@pxt.query
def review_queue() -> pxt.Query:
    return (
        Claims.where(Claims.route != "approve")
        .order_by(Claims.severity, asc=False)
        .select(Claims.id, Claims.product, Claims.route, Claims.damaged, Claims.consistent, Claims.severity)
    )


api = FastAPIRouter(name="claims", prefix="/api")
api.add_insert_route(
    Claims,
    path="/claims",
    uploadfile_inputs=[Claims.photo, Claims.voice_note],
    inputs=[Claims.product],
    outputs=[Claims.id, Claims.transcript, Claims.cause, Claims.severity, Claims.route, Claims.reply_text],
)
api.add_query_route(path="/similar", query=similar_claims, method="post")
api.add_query_route(path="/review", query=review_queue, method="get")
