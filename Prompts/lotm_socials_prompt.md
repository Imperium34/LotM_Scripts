# LOTM Social Caption & Carousel Generator

Creates eerie, atmospheric captions for TikTok/Instagram and generates ready-to-use terminal commands for the local `generate_carousel.py` script.

## Inputs Expected

Provide inputs using these structural tags:

- `<chapter_text>`: The finalized Turkish chapter translation.
- `<chapter_number>`: The chapter number (and optional title).

## Quote Selection & Chunking Criteria

Extract a high-impact scene from the chapter that fulfills these requirements:

- **Preserve Paragraph Structure:** Retain the original line breaks, dialogue formatting, and paragraph structure verbatim. Do NOT merge separate paragraphs or dialogue lines.
- **Atmospheric Impact:** Select a concise, high-impact scene (philosophical, ominous, or punchy dialogue).
- **Spoiler Prohibition:** Must NOT contain major plot twists, character deaths, or secret identity reveals.
- **Chunking Rule:** If the selected scene exceeds 4 short lines or contains multiple dense paragraphs, you MUST logically split the quote into two or three separate chunks (`[ALINTI BÖLÜM 1]`, `[ALINTI BÖLÜM 2]`, etc.) to be spread across multiple slides.

## Font Size Guidelines

- Font size must ALWAYS remain between `40` and `48` for maximum readability on mobile.
- Default to `44` for most multi-slide chunks.

## Output Generation Steps

1. **[BÖLÜM BAŞLIĞI]:** Format as `Bölüm [X]: [BAŞLIK]`
2. **[VURUCU ALINTI]:** Quote the selected text in quotation marks (`"..."`). If split, label them clearly (e.g., `Bölüm 1: "..."`, `Bölüm 2: "..."`).
3. **[PSİKOLOJİK KANCA VE SORU]:** Provide two distinct hook options:
   - **Seçenek A (Atmosferik/Korku):** Focuses on cosmic horror or mystical atmosphere.
   - **Seçenek B (Psikolojik/Zihinsel):** Focuses on character dilemmas or internal conflict.
     Follow each option with a single thought-provoking question for followers.
4. **[YÖNLENDİRME / CTA]:** Include the standard call-to-action:
   `"Esrarın Hükümdarı Bölüm [X] web sitemizde yayında. Sislerin ardındaki sırları okumak için bağlantı profilde. 🎩🩸"`
5. **[HASHTAGLER]:** Include exactly 5 rich, high-reach, thematic hashtags (e.g., `#esrarınhükümdarı`, `#lordofthemysteries`, `#lotm`, `#darkfantasy`, `#booktokturkiye`).
6. **[SLIDE ÜRETME KOMUTU]:** Provide a copy-pasteable terminal command for `generate_carousel.py`. Pass the chapter title first, followed by each quote chunk as a separate string argument, and end with the font size.

## Output Format

```markdown
1. [BÖLÜM BAŞLIĞI]
   Bölüm [X]: [BAŞLIK]

2. [VURUCU ALINTI]
   Bölüm 1: "[Chunk 1]"
   Bölüm 2: "[Chunk 2]" (If applicable)

3. [PSİKOLOJİK KANCA VE SORU]
   **Seçenek A (Atmosferik/Korku):**
   [Short commentary]
   [Challenging question]

**Seçenek B (Psikolojik/Zihinsel):**
[Short commentary]
[Challenging question]

4. [YÖNLENDİRME / CTA]
   Esrarın Hükümdarı Bölüm [X] web sitemizde yayında. Sislerin ardındaki sırları okumak için bağlantı profilde. 🎩🩸

5. [HASHTAGLER]
   [Exactly 5 enriched hashtags]

6. [SLIDE ÜRETME KOMUTU]
   `python generate_carousel.py "Bölüm [X]: [BAŞLIK]" "[Chunk 1]" "[Chunk 2]" [FONT_SIZE]`
```
