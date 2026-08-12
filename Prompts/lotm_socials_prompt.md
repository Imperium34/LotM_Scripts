LOTM Social Caption & Carousel Generator

Creates eerie, atmospheric captions for TikTok/Instagram and generates ready-to-use terminal commands for the local generate_carousel.py script.
Inputs Expected

Provide inputs using these structural tags:

    <chapter_text>: The finalized Turkish chapter translation.
    <chapter_number>: The chapter number (and optional title).

Quote Selection Criteria

Extract a quote of around 3 paragraphs from the chapter that fulfills these requirements:

    Atmospheric Impact: Prioritize eerie worldbuilding, mysterious Tarot Club / Fool interactions, or intense psychological tension.
    Formatting for Slide 1: Keep it engaging (around 3 paragraphs) so it fits elegantly on the carousel slides.
    Spoiler Prohibition: Must NOT contain major plot twists, character deaths, or secret identity reveals. It should entice without spoiling.

Output Generation Steps

    [BÖLÜM BAŞLIĞI]: Format as Bölüm [X]: [BAŞLIK]
    [VURUCU ALINTI]: Quote the selected ~3 paragraphs in quotation marks ("...").
    [PSİKOLOJİK KANCA VE SORU]: Provide two distinct hook options:
        Seçenek A (Atmosferik/Korku): Focuses on cosmic horror, Victorian dread, or mystical atmosphere.
        Seçenek B (Psikolojik/Zihinsel): Focuses on character dilemmas, internal conflict, or strategic tension. Follow each option with a single thought-provoking question for followers.
    [YÖNLENDİRME / CTA]: Include the standard call-to-action: "Esrarın Hükümdarı Bölüm [X] web sitemizde yayında. Sislerin ardındaki sırları okumak için bağlantı profilde. 🎩🩸"
    [HASHTAGLER]: Include exactly 5 rich, high-reach, thematic hashtags relevant to the chapter's tone/content (selected from enriched tags like #esrarınhükümdarı, #lordofthemysteries, #lotm, #darkfantasy, #karanlıkfantezi, #webnovel, #gizem, #booktokturkiye, #anime).
    [SLIDE ÜRETME KOMUTU]: Provide a copy-pasteable terminal command to generate the carousel slides instantly via generate_carousel.py: python generate_carousel.py "Bölüm [X]: [BAŞLIK]" "[VURUCU ALINTI]"

Output Format

1. [BÖLÜM BAŞLIĞI]
   Bölüm [X]: [BAŞLIK]

2. [VURUCU ALINTI]
   "[Selected quote text (~3 paragraphs)]"

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

```bash
python generate_carousel.py "Bölüm [X]: [BAŞLIK]" "[Selected quote text]"
```
