import re
import sys
import html
import shutil
import random
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
# turkce.py betiklerin kokunde (bir ust klasor): Turkce buyuk harf icin tek kaynak.
sys.path.insert(0, str(SCRIPT_DIR.parent))
from turkce import tr_buyuk_harf  # noqa: E402
DEFAULT_FONT_SIZE = 44  # Bumped up default to match new prompt rules
MIN_FONT_SIZE = 20
FONT_STEP = 2


def parse_args():
    """Accepts the chapter title plus an unlimited number of excerpt/quote
    strings as positional args. Font size moved to an explicit --font-size
    flag so there's no ambiguity with excerpts (e.g. a quote that ends in a
    bare number no longer risks being swallowed as the font size)."""
    parser = argparse.ArgumentParser(
        description="LotM Instagram carousel slide generator",
        add_help=True,
    )
    parser.add_argument(
        "title",
        nargs="?",
        default=None,
        help="Bölüm başlığı (ör. 'Bölüm 35: Malumat Takası')",
    )
    parser.add_argument(
        "excerpts",
        nargs="*",
        default=[],
        help="İstediğiniz kadar alıntı/parça metni, her biri ayrı bir argüman olarak",
    )
    parser.add_argument(
        "--font-size",
        "-f",
        dest="font_size",
        default=None,
        help=f"Font boyutu px cinsinden (varsayılan {DEFAULT_FONT_SIZE})",
    )

    ns = parser.parse_args()

    title = ns.title
    excerpts = list(ns.excerpts)
    font_size_arg = ns.font_size

    if not title:
        title = input("Bölüm Başlığı (ör. Bölüm 35: Malumat Takası): ").strip()

    if not excerpts:
        print("Alıntı Metinleri (Bitirmek için boş bırakıp Enter'a basın):")
        while True:
            chunk = input(f"Parça {len(excerpts) + 1}: ").strip()
            if not chunk:
                if len(excerpts) > 0:
                    break
                else:
                    print("Lütfen en az bir parça metin girin.")
                    continue
            excerpts.append(chunk)

    if not font_size_arg:
        font_size_arg = (
            input(f"Font Boyutu (varsayılan {DEFAULT_FONT_SIZE}): ").strip() or None
        )

    font_size = DEFAULT_FONT_SIZE
    if font_size_arg:
        cleaned = str(font_size_arg).replace("px", "").strip()
        if cleaned.isdigit():
            font_size = int(cleaned)
        else:
            print(
                f"Uyarı: geçersiz font boyutu '{font_size_arg}', varsayılan {DEFAULT_FONT_SIZE} kullanılacak."
            )

    return title, excerpts, font_size


def pick_backgrounds(folder_name, fallback_name, count):
    """Returns `count` background URIs, one per excerpt slide, drawn from
    folder_name's PNGs without repeating a background back-to-back (within
    this run, and across runs via the .last_bg state file) as long as more
    than one PNG is available. If there are fewer PNGs than slides, the
    pool is reshuffled and reused (still avoiding an immediate repeat at
    the reshuffle boundary where possible)."""
    bg_folder = SCRIPT_DIR / folder_name
    png_files = list(bg_folder.glob("*.png")) if bg_folder.is_dir() else []

    if not png_files:
        fallback = SCRIPT_DIR / fallback_name
        if not fallback.exists():
            raise FileNotFoundError(f"Fallback background not found: {fallback}")
        print(
            f"Uyarı: '{folder_name}' klasöründe png bulunamadı, varsayılan '{fallback_name}' kullanılıyor."
        )
        fallback_uri = fallback.resolve().as_uri()
        return [fallback_uri] * count

    state_path = SCRIPT_DIR / f".last_bg_{folder_name}.txt"
    last_used = None
    if state_path.exists():
        last_used = state_path.read_text(encoding="utf-8").strip()

    chosen = []
    prev_name = last_used
    pool = []

    for _ in range(count):
        if not pool:
            pool = png_files.copy()
            random.shuffle(pool)
            # Avoid picking the same file that ended the previous batch
            # (or the previous run) right at the start of a fresh shuffle.
            if len(pool) > 1 and pool[0].name == prev_name:
                pool[0], pool[1] = pool[1], pool[0]

        candidate = pool.pop(0)
        # Avoid an immediate back-to-back repeat within this run when an
        # alternative is available in the remaining pool.
        if candidate.name == prev_name and pool:
            candidate, pool[0] = pool[0], candidate

        chosen.append(candidate)
        prev_name = candidate.name

    print("Selected backgrounds: " + ", ".join(f.name for f in chosen))

    try:
        state_path.write_text(chosen[-1].name, encoding="utf-8")
    except OSError as e:
        print(f"Uyarı: son kullanılan arka plan kaydedilemedi: {e}")

    return [f.resolve().as_uri() for f in chosen]


ITALIC_PATTERN = re.compile(r"(?<!\w)_(\S(?:[^_\n]*\S)?)_(?!\w)")


def apply_italics(escaped_text):
    return ITALIC_PATTERN.sub(r"<em>\1</em>", escaped_text)


def paragraphs_to_html(text):
    # CLI args typed without ANSI-C quoting ($'...') arrive with literal
    # backslash-n (the two characters \ and n) instead of a real newline
    # byte, so normalize those to actual newlines before splitting.
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    text = text.strip()
    blocks = re.split(r"\n\s*\n", text)
    parts = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        escaped = apply_italics(html.escape(block)).replace("\n", "<br>")
        parts.append(f"<p>{escaped}</p>")
    return "".join(parts) if parts else f"<p>{apply_italics(html.escape(text))}</p>"


def font_setup():
    # (Remains unchanged)
    fonts_dir = SCRIPT_DIR / "fonts"
    font_files = {
        "Cinzel": [("Cinzel-SemiBold.woff2", "600"), ("Cinzel-Bold.woff2", "700")],
        "Lora": [
            ("Lora-Regular.woff2", "400"),
            ("Lora-Medium.woff2", "500"),
            ("Lora-Italic.woff2", "400", "italic"),
        ],
    }
    faces = []
    found_any = False
    for family, files in font_files.items():
        for entry in files:
            fname, weight = entry[0], entry[1]
            style = entry[2] if len(entry) > 2 else "normal"
            fpath = fonts_dir / fname
            if fpath.exists():
                found_any = True
                faces.append(
                    f"@font-face {{ font-family: '{family}'; "
                    f"src: url('{fpath.resolve().as_uri()}') format('woff2'); "
                    f"font-weight: {weight}; font-style: {style}; }}"
                )

    if found_any:
        return "\n".join(faces), ""

    google_link = (
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700'
        '&family=Lora:ital,wght@0,400;0,500;1,400&display=swap">'
    )
    return "", google_link


def build_html(
    title_upper_escaped, excerpts_html, font_size, bg_excerpt_uris, bg_cta_uri
):
    font_face_css, google_fonts_link = font_setup()

    # Generate HTML divs dynamically based on number of chunks. Each slide
    # gets its own background image via an inline style, since the shared
    # .excerpt-slide class no longer sets background-image.
    slides_html = []
    for i, exc_html in enumerate(excerpts_html):
        bg_uri = bg_excerpt_uris[i]
        slides_html.append(f"""
  <div id="slide_{i}" class="excerpt-slide" style="background-image: url('{bg_uri}');">
    <div class="excerpt-wrap" id="excerpt-wrap-{i}">{exc_html}</div>
  </div>""")

    return f"""
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  {google_fonts_link}
  <style>
    {font_face_css}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    .excerpt-slide {{
      width: 1080px; height: 1080px;
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
      font-family: 'Lora', serif;
      color: #f4f1ea;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      text-align: center;
      padding: 100px 90px;
      overflow: hidden;
    }}
    .excerpt-slide .excerpt-wrap {{
      font-size: {font_size}px;
      line-height: 1.65;
      max-width: 100%;
    }}
    .excerpt-slide p {{ margin-bottom: 24px; overflow-wrap: break-word; }}
    .excerpt-slide em {{ font-style: italic; }}

    .cta-slide {{
      width: 1080px; height: 1080px;
      background-image: url('{bg_cta_uri}');
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
      font-family: 'Cinzel', serif;
      color: #e5c158;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      align-items: center;
      text-align: center;
      padding: 100px 60px;
      text-transform: uppercase;
      letter-spacing: 2px;
      overflow: hidden;
    }}
    .cta-slide .top-header {{ font-size: 42px; font-weight: 700; line-height: 1.4; max-width: 900px; overflow-wrap: break-word; }}
    .cta-slide .bottom-cta {{ font-size: 48px; font-weight: 600; line-height: 1.5; }}
  </style>
</head>
<body>
  {"".join(slides_html)}
  <div id="slide_cta" class="cta-slide">
    <div class="top-header">{title_upper_escaped} YAYINDA.</div>
    <div class="bottom-cta">DEVAMINI OKUMAK İÇİN<br>BAĞLANTI PROFİLDE</div>
  </div>
</body>
</html>
"""


def render_slides(html_content, font_size, num_excerpts, out_dir):
    temp_html_path = SCRIPT_DIR / "temp_slides.html"
    temp_html_path.write_text(html_content, encoding="utf-8")

    generated_tmps = []
    final_names = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/chromium")
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.goto(temp_html_path.resolve().as_uri())

            # 1. Render all excerpt slides dynamically
            for i in range(num_excerpts):
                current_size = font_size
                fits = False

                # Shrink text logic for THIS specific chunk
                while current_size >= MIN_FONT_SIZE:
                    page.evaluate(
                        f"(size) => {{ document.getElementById('excerpt-wrap-{i}').style.fontSize = size + 'px'; }}",
                        current_size,
                    )
                    overflow = page.evaluate(
                        f"""() => {{
                            const el = document.getElementById('excerpt-wrap-{i}');
                            const parent = el.parentElement;
                            // clientHeight/clientWidth include the parent's
                            // OWN padding (100px/90px) -- comparing scroll
                            // size against them treats the padding band as
                            // usable text space, so borderline-long excerpts
                            // get accepted as "fits" while visually
                            // crowding out (or past) the intended margin.
                            // Subtract the real padding to compare against
                            // the actual available content box instead.
                            const cs = getComputedStyle(parent);
                            const availH = parent.clientHeight
                                - parseFloat(cs.paddingTop)
                                - parseFloat(cs.paddingBottom);
                            const availW = parent.clientWidth
                                - parseFloat(cs.paddingLeft)
                                - parseFloat(cs.paddingRight);
                            return el.scrollHeight > availH
                                || el.scrollWidth > availW;
                        }}"""
                    )
                    if not overflow:
                        fits = True
                        break
                    current_size -= FONT_STEP

                if not fits:
                    print(
                        f"Uyarı: Parça {i + 1} metni {MIN_FONT_SIZE}px boyutunda bile tam sığmadı."
                    )

                slide_tmp = out_dir / f"slide{i + 1}.png.tmp"
                page.locator(f"#slide_{i}").screenshot(path=str(slide_tmp), type="png")
                generated_tmps.append(slide_tmp)
                final_names.append(out_dir / f"slide{i + 1}.png")

            # 2. Render the final CTA slide
            cta_idx = num_excerpts + 1
            cta_tmp = out_dir / f"slide{cta_idx}.png.tmp"
            page.locator("#slide_cta").screenshot(path=str(cta_tmp), type="png")
            generated_tmps.append(cta_tmp)
            final_names.append(out_dir / f"slide{cta_idx}.png")

            browser.close()
    finally:
        if temp_html_path.exists():
            temp_html_path.unlink()

    # 3. Cleanup old slides to prevent 'zombie' images from previous longer carousels
    for old_file in out_dir.glob("slide*.png"):
        if old_file.is_file():
            old_file.unlink()

    # 4. Finalize new slides safely
    for tmp, final in zip(generated_tmps, final_names):
        shutil.move(str(tmp), str(final))

    return final_names


def main():
    title, excerpts, font_size = parse_args()

    # str.upper() Turkce degil: "Seyirci" -> "SEYIRCI", "Gündelik Ayin
    # İlmi" -> "GÜNDELIK AYIN İLMI" (ayın). Yayimlanan gorsellerde boyle
    # cikiyordu.
    title_upper_escaped = html.escape(tr_buyuk_harf(title))

    # Process html for each chunk separately
    excerpts_html = [paragraphs_to_html(exc) for exc in excerpts]

    bg_excerpt_uris = pick_backgrounds(
        "backgrounds_slide1", "bg_victorian.png", len(excerpts)
    )

    bg_cta_path = SCRIPT_DIR / "bg_tarot_club.png"
    if not bg_cta_path.exists():
        raise FileNotFoundError(f"Slide CTA background not found: {bg_cta_path}")
    bg_cta_uri = bg_cta_path.resolve().as_uri()

    html_content = build_html(
        title_upper_escaped, excerpts_html, font_size, bg_excerpt_uris, bg_cta_uri
    )

    final_slides = render_slides(html_content, font_size, len(excerpts), SCRIPT_DIR)

    print("\nOluşturulan Slaytlar:")
    for slide in final_slides:
        print(f" - {slide.name}")
    print("İşlem başarıyla tamamlandı!")


if __name__ == "__main__":
    main()
