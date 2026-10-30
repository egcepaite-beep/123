"""Runs one campaign: brief -> hero frame -> remaining frames -> ads, email, board, zip."""
import io
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

import brief as brief_mod
import images

TEMPLATES = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def live_text() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def live_images() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def run(job_dir: Path, product_bytes: bytes, style_bytes: bytes | None, *, brand: str,
        notes: str, language: str, num_posts: int, progress) -> None:
    img_dir = job_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    product_jpeg = brief_mod.to_jpeg(product_bytes)
    style_jpeg = brief_mod.to_jpeg(style_bytes) if style_bytes else None
    (img_dir / "product.jpg").write_bytes(product_jpeg)
    product = Image.open(io.BytesIO(product_jpeg))
    style = Image.open(io.BytesIO(style_jpeg)) if style_jpeg else None

    progress("Kuriama kampanijos koncepcija" + ("" if live_text() else " (demo)"))
    if live_text():
        b = brief_mod.write_brief(product_jpeg, style_jpeg, brand=brand, notes=notes,
                                  language=language, num_posts=num_posts)
    else:
        b = brief_mod.demo_brief(brand=brand, num_posts=num_posts, language=language)
    (job_dir / "brief.json").write_text(b.model_dump_json(indent=2), encoding="utf-8")

    def make(index: int, role: str, scene: str, aspect: str, hero: Image.Image | None) -> Image.Image:
        if not live_images():
            return images.demo_image(product, b.palette, aspect, index)
        refs = [product] + ([hero] if hero else []) + ([style] if style else [])
        prompt = images.frame_prompt(b, scene, role, hero is not None, style is not None)
        return images.generate_image(prompt, refs, aspect)

    def save(img: Image.Image, name: str) -> str:
        img.convert("RGB").save(img_dir / name, "JPEG", quality=90)
        return f"images/{name}"

    shots = b.shots[:num_posts]
    progress("Generuojamas pagrindinis kadras" + ("" if live_images() else " (demo)"))
    hero = make(0, shots[0].role, shots[0].scene, "4:5", None)
    shot_files = [save(hero, f"01-{shots[0].role.lower()}.jpg")] + [""] * (len(shots) - 1)

    progress(f"Generuojami likę kadrai, reklamos ir baneris ({len(shots) - 1 + len(b.ads) + 1} vaizdai)")
    with ThreadPoolExecutor(max_workers=4) as pool:
        shot_jobs = {i: pool.submit(make, i, s.role, s.scene, "4:5", hero) for i, s in enumerate(shots) if i}
        ad_jobs = [pool.submit(make, 10 + i, "AD", a.scene, "9:16", hero) for i, a in enumerate(b.ads)]
        banner_job = pool.submit(make, 20, "BANNER", b.banner.scene, "16:9", hero)
        for i, job in shot_jobs.items():
            shot_files[i] = save(job.result(), f"{i + 1:02d}-{shots[i].role.lower()}.jpg")
        ad_photos = [j.result() for j in ad_jobs]
        banner_file = save(banner_job.result(), "banner.jpg")

    progress("Maketuojamos reklamos, email ir kampanijos lenta")
    ad_files = []
    for i, (ad, photo) in enumerate(zip(b.ads, ad_photos), start=1):
        images.render_ad(photo, b.brand_name, ad.headline, ad.cta).save(img_dir / f"ad-{i}.png")
        ad_files.append(f"images/ad-{i}.png")

    detail_file = next((f for f, s in zip(shot_files, shots) if s.role == "DETAIL"), shot_files[0])
    ctx = dict(b=b, shots=list(zip(shots, shot_files)), ads=list(zip(b.ads, ad_files)),
               banner_file=banner_file, detail_file=detail_file,
               demo_text=not live_text(), demo_images=not live_images())
    (job_dir / "email.html").write_text(TEMPLATES.get_template("email.html").render(**ctx), encoding="utf-8")
    (job_dir / "board.html").write_text(TEMPLATES.get_template("board.html").render(**ctx), encoding="utf-8")
    (job_dir / "captions.txt").write_text(captions_text(b, shots), encoding="utf-8")

    shutil.make_archive(str(job_dir.parent / f"{job_dir.name}-campaign"), "zip", root_dir=job_dir)
    progress("Baigta")


def captions_text(b, shots) -> str:
    parts = [f"{b.brand_name} - {b.concept_name}", b.tagline, ""]
    for i, s in enumerate(shots, start=1):
        parts += [f"{i:02d} {s.role}", s.caption, " ".join(s.hashtags), ""]
    parts += ["META ADS"]
    for i, a in enumerate(b.ads, start=1):
        parts += [f"{i}. {a.headline} | {a.cta}", a.primary_text, ""]
    parts += ["EMAIL", f"Subject: {b.email.subject}", f"Preheader: {b.email.preheader}"]
    return "\n".join(parts)
