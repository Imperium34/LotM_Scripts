import os
import re
import zipfile

# --- CONFIGURATION ---
EPUB_FILE = "Lord_of_the_Mysteries.epub"
OUTPUT_DIR = "LotM_Volumes"

# Official Lord of the Mysteries volume ranges (inclusive)
VOLUME_RANGES = [
    {"num": 1, "name": "Clown", "start": 1, "end": 210},
    {"num": 2, "name": "Faceless", "start": 211, "end": 482},
    {"num": 3, "name": "Traveler", "start": 483, "end": 732},
    {"num": 4, "name": "The_Red_Priest", "start": 733, "end": 946},
    {"num": 5, "name": "Red_Chaser", "start": 947, "end": 1149},
    {"num": 6, "name": "Light_Seeker", "start": 1150, "end": 1266},
    {"num": 7, "name": "The_Hanged_Man", "start": 1267, "end": 1348},
    {"num": 8, "name": "Ordinary_Persons_Daily_Life", "start": 1349, "end": 9999},
]
# ---------------------


def clean_html(html_content):
    """Removes HTML tags and returns plain text."""
    html_content = re.sub(r"<script.*?>.*?</script>", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"<style.*?>.*?</style>", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"</p>|<br\s*/?>|</div>", "\n", html_content)
    text = re.sub(r"<[^>]+>", "", html_content)

    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return text


def get_volume_for_chapter(chapter_num):
    """Returns the volume dictionary for a given chapter number."""
    for vol in VOLUME_RANGES:
        if vol["start"] <= chapter_num <= vol["end"]:
            return vol
    return None


def split_epub_by_chapters(epub_path, output_folder):
    if not os.path.exists(epub_path):
        print(f"Error: Could not find '{epub_path}'.")
        return

    os.makedirs(output_folder, exist_ok=True)
    print(f"Reading {epub_path}...")

    # Dictionary to hold the final text for each volume
    volume_texts = {vol["num"]: [] for vol in VOLUME_RANGES}
    current_volume_num = 1  # Default starting volume

    # 1. Extract and process files chronologically
    with zipfile.ZipFile(epub_path, "r") as archive:
        for file_info in sorted(archive.infolist(), key=lambda x: x.filename):
            if file_info.filename.endswith((".html", ".xhtml")):
                with archive.open(file_info) as f:
                    raw_html = f.read().decode("utf-8", errors="ignore")
                    text_block = clean_html(raw_html).strip()

                    if not text_block:
                        continue

                    # 2. Check if this text block starts a new chapter
                    # Matches "Chapter 123", "CHAPTER 123", "Chapter 123: Title" etc.
                    chapter_match = re.match(
                        r"^Chapter\s+(\d+)", text_block, re.IGNORECASE
                    )

                    if chapter_match:
                        chapter_num = int(chapter_match.group(1))
                        # Find which volume this chapter belongs to
                        assigned_vol = get_volume_for_chapter(chapter_num)
                        if assigned_vol:
                            current_volume_num = assigned_vol["num"]

                    # Append the text to the currently active volume
                    volume_texts[current_volume_num].append(text_block)

    # 3. Save the compiled volumes into separate files
    print("\nWriting volume files...")
    for vol in VOLUME_RANGES:
        vol_num = vol["num"]
        vol_name = vol["name"]
        content = "\n\n".join(volume_texts[vol_num]).strip()

        if content:
            filename = f"Volume_{vol_num}_{vol_name}.txt"
            filepath = os.path.join(output_folder, filename)
            with open(filepath, "w", encoding="utf-8") as out_file:
                out_file.write(content)
            print(f"Saved: {filename}")
        else:
            print(f"Warning: No content found for Volume {vol_num}")

    print(f"\nDone! Check the '{output_folder}' directory.")


if __name__ == "__main__":
    split_epub_by_chapters(EPUB_FILE, OUTPUT_DIR)
