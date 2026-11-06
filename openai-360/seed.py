"""uv run python seed.py claims: generate four demo claims, then file them as claims."""

import sys

import app

DEMO_CLAIMS = [
    {
        "product": "smartphone",
        "photo_prompt": "Phone photo of a smartphone on a kitchen table with a badly cracked screen, natural light",
        "story": "Hi, I dropped my phone on the kitchen floor this morning and the screen cracked. "
        "It still turns on but I can't read anything.",
    },
    {
        "product": "wireless headphones",
        "photo_prompt": "Phone photo of over-ear headphones on a desk, one ear cup snapped off the headband",
        "story": "The left ear cup on my headphones snapped off the band. I only had them for two weeks "
        "and I never dropped them.",
    },
    {
        "product": "laptop",
        "photo_prompt": "Phone photo of a closed silver laptop on a desk, clean and undamaged",
        "story": "My laptop arrived with a shattered screen. The whole display is smashed.",
    },
    {
        "product": "coffee maker",
        "photo_prompt": "Phone photo of a clean drip coffee maker on a counter, nothing visibly wrong",
        "story": "My coffee maker stopped heating after a month. The water comes out cold.",
    },
]

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "claims"
    app.TableModel.bind_all(target)
    app.DemoInputs.insert(DEMO_CLAIMS)
    demo = app.DemoInputs.select(app.DemoInputs.product, app.DemoInputs.photo, app.DemoInputs.voice_note)
    app.Claims.insert(list(demo.collect()))
    print(app.Claims.select(app.Claims.product, app.Claims.route, app.Claims.damaged, app.Claims.consistent).collect())
