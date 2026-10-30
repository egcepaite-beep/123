"""Campaign brief: Claude reads the product photo and writes the whole 360 plan."""
import base64
import io
import os

from pydantic import BaseModel, Field

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

# The nine shot roles from the reference board, in board order.
SHOT_ROLES = [
    "HERO", "PORTRAIT", "LIFESTYLE", "DETAIL", "BEAUTY",
    "ENVIRONMENT", "RITUAL", "REFLECTION", "CLOSING",
]


class Shot(BaseModel):
    role: str = Field(description="One of the shot roles, e.g. HERO, PORTRAIT")
    scene: str = Field(description="English image prompt for this frame only: framing, pose, action, where the product is")
    caption: str = Field(description="Social caption for this post, in the campaign language")
    hashtags: list[str]


class Ad(BaseModel):
    headline: str = Field(description="2-4 words, set on the ad image")
    primary_text: str = Field(description="Meta ad primary text")
    cta: str = Field(description="Button label, uppercase, 1-3 words")
    scene: str = Field(description="English image prompt for a vertical 9:16 ad frame")


class Banner(BaseModel):
    headline: str
    subline: str
    cta_primary: str
    cta_secondary: str
    scene: str = Field(description="English image prompt for a wide 16:9 frame with empty space on the left for text")


class Email(BaseModel):
    subject: str
    preheader: str
    hero_headline: str
    hero_text: str
    cta: str
    section_title: str
    section_text: str


class Brief(BaseModel):
    brand_name: str
    product_name: str
    concept_name: str = Field(description="Campaign idea in a few words, e.g. 'The Art of Stillness'")
    tagline: str
    concept_summary: str = Field(description="2-3 sentences: the idea, the feeling, why it fits the product")
    palette: list[str] = Field(description="4-5 hex colours taken from the planned imagery")
    visual_style: str = Field(description="English style prompt shared by every frame: light, time of day, film look, colour grade, lens")
    model_description: str = Field(description="English description of the one recurring (fictional) model: look, hair, makeup")
    wardrobe: str
    location: str
    product_description: str = Field(description="English description of the product exactly as in the photo: shape, cap, label, liquid colour")
    shots: list[Shot]
    ads: list[Ad] = Field(description="Exactly 3 Meta ad variations")
    banner: Banner
    email: Email


SYSTEM = """You are the creative director of a premium marketing studio.
From one product photo you plan a complete, coherent 360 campaign: social posts,
Meta ads, a website hero banner and an email, all in one visual world.

Rules:
- Every image is shot in the same world: the same location, the same light, the
  same colour grade and the same single fictional model. Write visual_style,
  model_description, wardrobe and location so they can be pasted into every prompt.
- The product must stay exactly as in the photo (shape, cap, label text). Describe it
  precisely in product_description; scenes say where it sits, never redesign it.
- The model is a fictional person. Never describe or name a real person or celebrity.
- Image prompts (scene, visual_style, ...) are in English. All copy the audience reads
  (captions, ads, banner, email, tagline, concept) is in the campaign language.
- Copy is short, confident and premium: no exclamation marks, no emoji in headlines.
"""


def _image_block(data: bytes) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg",
                   "data": base64.standard_b64encode(data).decode()},
    }


def write_brief(product_jpeg: bytes, style_jpeg: bytes | None, *, brand: str,
                notes: str, language: str, num_posts: int) -> Brief:
    import anthropic

    roles = ", ".join(SHOT_ROLES[:num_posts])
    content = [_image_block(product_jpeg)]
    if style_jpeg:
        content.append(_image_block(style_jpeg))
    content.append({"type": "text", "text": (
        f"The first image is the product photo."
        + (" The second image is a mood reference: match its mood, light and styling, not its product." if style_jpeg else "")
        + f"\n\nBrand: {brand or 'read it from the label'}"
        + f"\nNotes from the client: {notes or 'none'}"
        + f"\nCampaign language: {language}"
        + f"\nPlan exactly {num_posts} social posts with these roles, in this order: {roles}."
        + "\nPlan exactly 3 Meta ads, one banner and one email."
    )})

    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high"},
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_format=Brief,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to plan this campaign.")
    return response.parsed_output


def demo_brief(*, brand: str, num_posts: int, language: str) -> Brief:
    """A fixed brief used when ANTHROPIC_API_KEY is not set, so the app can be tried end to end."""
    brand = brand or "Maison Lumen"
    lt = language.lower().startswith("l")
    t = (lambda a, b: a) if lt else (lambda a, b: b)
    captions = [
        t("Tylos menas. Susipažinkite su kvapu, sukurtu iš šviesos ir ramybės.", "The art of stillness. Meet a scent shaped by light and silence."),
        t("Ne garsiai. Ne trumpam. Kvapas, kuris lieka šalia.", "Not loud. Not fleeting. A scent that stays close."),
        t("Tiems, kurie nesivaiko dėmesio – jie jį išlaiko.", "For the ones who don't chase attention - they hold it."),
        t("Detalės, kurias pastebi tik tie, kurie žiūri lėtai.", "Details for those who look slowly."),
        t("Šviesa ant odos. Kvapas ant pulso.", "Light on skin. Scent on the pulse."),
        t("Akmuo, jūra, tyla.", "Stone, sea, silence."),
        t("Kasdienis ritualas, kuris sulėtina laiką.", "A daily ritual that slows time down."),
        t("Atspindys to, kas tikra.", "A reflection of what is real."),
        t(f"{brand}. Tyli prabanga.", f"{brand}. Quiet luxury, bottled."),
    ]
    return Brief(
        brand_name=brand,
        product_name="Eau de Parfum",
        concept_name=t("Tylos menas", "The Art of Stillness"),
        tagline=t("Tylos menas", "The Art of Stillness"),
        concept_summary=t(
            "Kampanija apie ramų pasitikėjimą: šilta vakaro šviesa, akmenys prie jūros ir vienas veidas. Produktas yra kiekviename kadre kaip tylus akcentas.",
            "A campaign about quiet confidence: warm evening light, coastal stone and one face. The product sits in every frame as a calm accent."),
        palette=["#F3EEE6", "#D9C9B3", "#B08A5A", "#5B4636", "#1E1A17"],
        visual_style="golden hour, soft warm sidelight, analog film grain, muted warm grade, 85mm editorial fashion photography",
        model_description="fictional woman in her late twenties, long dark wavy hair, natural makeup, small gold hoop earrings",
        wardrobe="flowing ivory silk and linen",
        location="pale limestone rocks above a calm sea",
        product_description="the product exactly as in the photo",
        shots=[Shot(role=r, scene=f"{r.lower()} frame", caption=captions[i],
                    hashtags=["#" + brand.replace(" ", ""), t("#tylosmenas", "#theartofstillness"), "#eaudeparfum"])
               for i, r in enumerate(SHOT_ROLES[:num_posts])],
        ads=[
            Ad(headline=t("Tylos menas", "The Art of Stillness"), primary_text=captions[0], cta=t("PIRKTI", "SHOP NOW"), scene="portrait"),
            Ad(headline=t("Tylus parašas", "A Quiet Signature"), primary_text=captions[2], cta=t("SUŽINOTI", "DISCOVER MORE"), scene="lifestyle"),
            Ad(headline=t("Esatis, išpilstyta.", "Presence, Bottled."), primary_text=captions[1], cta=t("ATRASTI KVAPĄ", "DISCOVER THE FRAGRANCE"), scene="product"),
        ],
        banner=Banner(
            headline=t("Tylos menas", "The Art of Stillness"),
            subline=t("Atraskite ramaus pasitikėjimo kvapą.", "Discover a fragrance of quiet confidence and lasting presence."),
            cta_primary=t("PIRKTI", "SHOP NOW"), cta_secondary=t("ISTORIJA", "DISCOVER THE STORY"), scene="wide"),
        email=Email(
            subject=t(f"{brand}: tylos menas", f"{brand}: the art of stillness"),
            preheader=t("Naujas kvapas tiems, kurie nesivaiko dėmesio.", "A new scent for those who don't chase attention."),
            hero_headline=t("Tylos menas", "The Art of Stillness"),
            hero_text=t("Rafinuotas kvapas, sukurtas ramaus pasitikėjimo akimirkoms.", "A refined Eau de Parfum created for moments of quiet confidence."),
            cta=t("ATRASTI KVAPĄ", "DISCOVER THE FRAGRANCE"),
            section_title=t("Kvapas, kuris lieka šalia", "A scent that stays close"),
            section_text=t("Tai kvietimas sulėtinti. Švelnus, bet įsimenamas, intymus, bet išraiškingas.",
                           "An invitation to slow down. Soft yet memorable, intimate yet expressive."),
        ),
    )


def to_jpeg(data: bytes, max_side: int = 1568) -> bytes:
    """Normalise any uploaded image to an RGB JPEG the APIs accept."""
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()
