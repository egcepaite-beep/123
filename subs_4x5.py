#!/usr/bin/env python3
"""Burn subtitles into a 4:5 video so they stay inside the centered 1:1 safe area.

A 4:5 video (e.g. 1080x1350) shown in a 1:1 placement is cropped to the
centered square (1080x1080), losing (H - W) / 2 px at the top and bottom.
This script keeps subtitles horizontally centered and inside that square,
so they are visible in both 4:5 and 1:1 placements.

If the input is not 4:5, it is first center-cropped to 4:5 (use --face-y to
shift the crop so the face stays inside the 1:1 area).

Usage:
    python3 subs_4x5.py input.mp4 subs.srt output.mp4
    python3 subs_4x5.py input.mp4 subs.srt preview.mp4 --guide   # draw 1:1 box
    python3 subs_4x5.py input.mp4 subs.srt output.mp4 --position center
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile


def probe_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:stream_side_data=rotation",
         "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    stream = json.loads(out)["streams"][0]
    w, h = stream["width"], stream["height"]
    rotation = 0
    for sd in stream.get("side_data_list", []):
        rotation = int(sd.get("rotation", 0))
    if abs(rotation) in (90, 270):
        w, h = h, w
    return w, h


def srt_time_to_ass(t):
    hh, mm, rest = t.strip().replace(".", ",").split(":")
    ss, ms = rest.split(",")
    return f"{int(hh)}:{int(mm):02d}:{int(ss):02d}.{int(ms) // 10:02d}"


def parse_srt(path):
    with open(path, encoding="utf-8-sig") as f:
        blocks = re.split(r"\n\s*\n", f.read().replace("\r\n", "\n").strip())
    events = []
    for block in blocks:
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            m = re.match(r"(\S+)\s*-->\s*(\S+)", line)
            if m:
                text = "\\N".join(lines[i + 1:])
                text = re.sub(r"</?(i|b|u)>", lambda t: {
                    "<i>": "{\\i1}", "</i>": "{\\i0}", "<b>": "{\\b1}",
                    "</b>": "{\\b0}", "<u>": "{\\u1}", "</u>": "{\\u0}"}[t.group(0)], text)
                text = re.sub(r"<[^>]+>", "", text)
                events.append((srt_time_to_ass(m.group(1)), srt_time_to_ass(m.group(2)), text))
                break
    return events


def build_ass(events, w, h, args):
    square = min(w, h)
    top = (h - square) // 2              # first visible row in 1:1 crop
    side = round(w * args.side_margin)    # horizontal safe padding
    font_size = round(w * args.font_scale)

    if args.position == "center":
        alignment, margin_v = 5, 0        # middle-center of the frame
    else:
        # bottom-center, lifted so the bottom line sits inside the 1:1 square
        alignment = 2
        margin_v = top + round(square * args.bottom_offset)

    style = (f"Style: Default,{args.font},{font_size},&H00FFFFFF,&H00FFFFFF,"
             f"&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
             f"{max(2, round(font_size * 0.08))},0,{alignment},{side},{side},{margin_v},1")
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style, "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines += [f"Dialogue: 0,{s},{e},Default,,0,0,0,,{t}" for s, e, t in events]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("srt")
    p.add_argument("output")
    p.add_argument("--position", choices=["bottom", "center"], default="bottom",
                   help="bottom = lower part of the 1:1 square (default, keeps face clear); "
                        "center = exact middle of the frame")
    p.add_argument("--bottom-offset", type=float, default=0.12,
                   help="distance of the subtitle baseline from the 1:1 square bottom, "
                        "as a fraction of the square (default 0.12)")
    p.add_argument("--font", default="Inter")
    p.add_argument("--font-scale", type=float, default=0.055,
                   help="font size as a fraction of video width (default 0.055)")
    p.add_argument("--side-margin", type=float, default=0.08,
                   help="left/right padding as a fraction of width (default 0.08)")
    p.add_argument("--face-y", type=float, default=0.5,
                   help="when cropping a non-4:5 input: vertical crop anchor 0..1 "
                        "(0 = keep top, 0.5 = center, 1 = keep bottom)")
    p.add_argument("--guide", action="store_true",
                   help="draw the 1:1 safe area box (for previewing face/subtitle placement)")
    p.add_argument("--crf", default="18")
    args = p.parse_args()

    src_w, src_h = probe_size(args.video)
    filters = []
    # Crop to 4:5 if needed
    if abs(src_w / src_h - 4 / 5) > 0.01:
        if src_w / src_h > 4 / 5:
            w, h = (src_h * 4 // 5) // 2 * 2, src_h // 2 * 2
            filters.append(f"crop={w}:{h}:(iw-{w})/2:0")
        else:
            w, h = src_w // 2 * 2, (src_w * 5 // 4) // 2 * 2
            filters.append(f"crop={w}:{h}:0:(ih-{h})*{args.face_y}")
    else:
        w, h = src_w, src_h

    ass = build_ass(parse_srt(args.srt), w, h, args)
    with tempfile.TemporaryDirectory() as tmp:
        ass_path = os.path.join(tmp, "subs.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass)
        if args.guide:
            top = (h - w) // 2
            filters.append(f"drawbox=x=0:y={top}:w={w}:h={w}:color=red@0.8:t=4")
        filters.append(f"ass={ass_path}")
        cmd = ["ffmpeg", "-y", "-i", args.video, "-vf", ",".join(filters),
               "-c:v", "libx264", "-crf", args.crf, "-preset", "medium",
               "-pix_fmt", "yuv420p", "-c:a", "copy", args.output]
        print(" ".join(cmd), file=sys.stderr)
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
