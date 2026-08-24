import re
import sys
import html
import shutil
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FONT_SIZE = 44  # Bumped up default to match new prompt rules
MIN_FONT_SIZE = 20
FONT_STEP = 2


def parse_args():
    """Handles an arbitrary number of quote chunks passed between the title
    and the font size parameter."""
    args = sys.argv[1:]
    title = None
    excerpts = []
    font_size_arg = None

    if len(args) > 0:
        title = args[0]
    if len(args) > 1:
        # Check if the very last argument is the font size
        last_arg = args[-1].replace("px", "").strip()
        if last_arg.isdigit():
            font_size_arg = args[-1]
            excerpts = args[1:-1]
        else:
            excerpts = args[1:]

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
        cleaned = font_size_arg.replace("px", "").strip()
        if cleaned.isdigit():
            font_size = int(cleaned)
        else:
            print(
                f"Uyarı: geçersiz font boyutu '{font_size_arg}', varsayılan {DEFAULT_FONT_SIZE} kullanılacak."
            )

    return title, excerpts, font_size


def pick_background(folder_name, fallback_name):
    # (Remains unchanged - handles background selection perfectly)
    bg_folder = SCRIPT_DIR / folder_name
    png_files = list(bg_folder.glob("*.png")) if bg_folder.is_dir() else []

    if png_files:
        state_path = SCRIPT_DIR / f".last_bg_{folder_name}.txt"
        last_used = None
        if state_path.exists():
            last_used = state_path.read_text(encoding="utf-8").strip()

        candidates = [f for f in png_files if f.name != last_used]
        if not candidates:
            candidates = png_files

        chosen = random.choice(candidates)
        print(f"Selected background: {chosen.name}")

        try:
            state_path.write_text(chosen.name, encoding="utf-8")
        except OSError as e:
            print(f"Uyarı: son kullanılan arka plan kaydedilemedi: {e}")

        return chosen.resolve().as_uri()

    fallback = SCRIPT_DIR / fallback_name
    if not fallback.exists():
        raise FileNotFoundError(f"Fallback background not found: {fallback}")
    print(
        f"Uyarı: '{folder_name}' klasöründe png bulunamadı, varsayılan '{fallback_name}' kullanılıyor."
    )
    return fallback.resolve().as_uri()


ITALIC_PATTERN = re.compile(r"(?<!\w)_(\S(?:[^_\n]*\S)?)_(?!\w)")


def apply_italics(escaped_text):
    return ITALIC_PATTERN.sub(r"<em>\1</em>", escaped_text)


def paragraphs_to_html(text):
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
    title_upper_escaped, excerpts_html, font_size, bg_excerpt_uri, bg_cta_uri
):
    font_face_css, google_fonts_link = font_setup()

    # Generate HTML divs dynamically based on number of chunks
    slides_html = []
    for i, exc_html in enumerate(excerpts_html):
        slides_html.append(f"""
  <div id="slide_{i}" class="excerpt-slide">
    <div class="excerpt-wrap" id="excerpt-wrap-{i}">{exc_html}</div>
  </div>""")

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {google_fonts_link}
  <style>
    {font_face_css}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    .excerpt-slide {{
      width: 1080px; height: 1080px;
      background-image: url('{bg_excerpt_uri}');
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
            page.goto(f"file://{temp_html_path}")

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
                            return el.scrollHeight > el.parentElement.clientHeight
                                || el.scrollWidth > el.parentElement.clientWidth;
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

    title_upper_escaped = html.escape(title.upper())

    # Process html for each chunk separately
    excerpts_html = [paragraphs_to_html(exc) for exc in excerpts]

    bg_excerpt_uri = pick_background("backgrounds_slide1", "bg_victorian.png")

    bg_cta_path = SCRIPT_DIR / "bg_tarot_club.png"
    if not bg_cta_path.exists():
        raise FileNotFoundError(f"Slide CTA background not found: {bg_cta_path}")
    bg_cta_uri = bg_cta_path.resolve().as_uri()

    html_content = build_html(
        title_upper_escaped, excerpts_html, font_size, bg_excerpt_uri, bg_cta_uri
    )

    final_slides = render_slides(html_content, font_size, len(excerpts), SCRIPT_DIR)

    print("\nOluşturulan Slaytlar:")
    for slide in final_slides:
        print(f" - {slide.name}")
    print("İşlem başarıyla tamamlandı!")


if __name__ == "__main__":
    main()
