"""Campaign imagery: Gemini image generation, demo placeholders and ad rendering."""
import io
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-2.5-flash-image")

SERIF_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "C:/Windows/Fonts/georgia.ttf",
]
SANS_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def frame_prompt(brief, scene: str, role: str, has_hero: bool, has_style: bool) -> str:
    refs = ["The first attached image is the product: reproduce it exactly, same shape, cap, label and label text."]
    if has_hero:
        refs.append("The second attached image is the campaign hero frame: match its model, wardrobe, location, light and colour grade exactly, as if shot the same day.")
    if has_style:
        refs.append("The last attached image is a mood reference: follow its mood and styling only.")
    return (
        f"Editorial luxury campaign photograph for {brief.brand_name}, shot role: {role}.\n"
        f"Scene: {scene}\n"
        f"Style: {brief.visual_style}.\n"
        f"Location: {brief.location}.\n"
        f"Model (fictional person, when the scene has one): {brief.model_description}, wearing {brief.wardrobe}.\n"
        f"Product: {brief.product_description}.\n"
        + " ".join(refs)
        + "\nNo added text, captions, logos or watermarks."
    )


def generate_image(prompt: str, refs: list[Image.Image], aspect: str) -> Image.Image:
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt, *refs],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect),
        ),
    )
    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            if part.inline_data and part.inline_data.data:
                return Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
    raise RuntimeError(f"The image model returned no image for: {role_of(prompt)}")


def role_of(prompt: str) -> str:
    return prompt.split("shot role: ", 1)[-1].split(".", 1)[0]


# --- Demo placeholders -------------------------------------------------------

ASPECT_SIZES = {"4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def cutout(product: Image.Image) -> Image.Image:
    """Drop a near-white studio background so the product can sit on any scene.

    Only white connected to the photo's edges is removed, so a white label stays.
    """
    rgb = product.convert("RGB")
    light = ImageOps.grayscale(rgb).point(lambda v: 255 if v > 238 else 0)
    w, h = light.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        if light.getpixel(corner) == 255:
            ImageDraw.floodfill(light, corner, 128)
    mask = light.point(lambda v: 0 if v == 128 else 255).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(2))
    out = rgb.convert("RGBA")
    out.putalpha(mask)
    bbox = mask.getbbox()
    return out.crop(bbox) if bbox else out


def demo_image(product: Image.Image, palette: list[str], aspect: str, index: int) -> Image.Image:
    """A styled stand-in frame: palette gradient, grain, the real product with a shadow."""
    w, h = ASPECT_SIZES.get(aspect, (1080, 1350))
    rnd = random.Random(index)
    colours = [_hex(c) for c in palette] or [(240, 235, 228), (90, 70, 55)]
    top = colours[(index) % len(colours)]
    bottom = colours[(index + 2) % len(colours)]
    grad = Image.linear_gradient("L").resize((w, h))
    bg = Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), grad)
    noise = Image.effect_noise((w, h), 18).convert("RGB")
    bg = Image.blend(bg, noise, 0.06)

    item = cutout(product)
    scale = [0.55, 0.38, 0.30, 0.75, 0.42, 0.28, 0.45, 0.50, 0.36][index % 9]
    target_h = int(h * scale)
    item = item.resize((max(1, int(item.width * target_h / item.height)), target_h))
    x = int((w - item.width) * rnd.uniform(0.3, 0.7))
    y = int((h - item.height) * rnd.uniform(0.55, 0.8))
    shadow = Image.new("RGBA", item.size, (0, 0, 0, 0))
    shadow.putalpha(item.getchannel("A").point(lambda v: v * 0.45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    bg.paste(shadow, (x + 18, y + 24), shadow)
    bg.paste(item, (x, y), item)
    return bg


# --- Ad rendering ------------------------------------------------------------

def _font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def render_ad(photo: Image.Image, brand: str, headline: str, cta: str) -> Image.Image:
    """A 1080x1920 Meta story ad: photo, dark fade, brand, serif headline, outlined button."""
    w, h = 1080, 1920
    img = ImageOps.fit(photo.convert("RGB"), (w, h))
    fade = Image.linear_gradient("L").resize((w, h)).point(lambda v: max(0, (v - 90) * 1.6))
    img = Image.composite(Image.new("RGB", (w, h), (18, 15, 13)), img, fade)
    top_fade = Image.linear_gradient("L").rotate(180).resize((w, h)).point(lambda v: max(0, (v - 200) * 2.2))
    img = Image.composite(Image.new("RGB", (w, h), (18, 15, 13)), img, top_fade)
    draw = ImageDraw.Draw(img)

    brand_font = _font(SERIF_FONTS, 44)
    spaced = "  ".join(brand.upper())
    draw.text((w / 2, 120), spaced, font=brand_font, fill=(245, 240, 232), anchor="mm")

    head_font = _font(SERIF_FONTS, 120)
    lines = _wrap(draw, headline, head_font, w - 200)
    y = 1430 - (len(lines) - 1) * 130
    for line in lines:
        draw.text((w / 2, y), line, font=head_font, fill=(245, 240, 232), anchor="mm")
        y += 130

    cta_font = _font(SANS_FONTS, 34)
    tw = draw.textlength(cta.upper(), font=cta_font)
    bw, bh = tw + 110, 96
    bx, by = (w - bw) / 2, 1660
    draw.rectangle((bx, by, bx + bw, by + bh), outline=(245, 240, 232), width=3)
    draw.text((w / 2, by + bh / 2), cta.upper(), font=cta_font, fill=(245, 240, 232), anchor="mm")
    return img
