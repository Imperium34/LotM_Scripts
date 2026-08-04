---
name: lotm-chapter-translator
description: "Translate Lord of the Mysteries / Gizemlerin Efendisi chapters from the Chinese RAW (with the English as a positioning map only) into literary Turkish, governed by the Sabit Çekirdek system prompt and the chapter's Bölüm Açılış Şablonu. Use whenever the user supplies an LotM chapter for translation, pastes a Bölüm Açılış Şablonu, or asks to continue translating a chapter in progress — including casual phrasings like 'şu bölümü çevirelim' or 'devam et'."
---

# LOTM Chapter Translator

## PRECONDITION — check before translating a single line

This skill **does not contain the translation rules.** They live in the Sabit Çekirdek (v4), which must be loaded as the session's system prompt. The core is the single source of truth: narrator voice, banned syntax patterns, the heavy-word quota, the _fark etti / anladı / idrak etti_, _gördü / seçti / algıladı_ and _irkildi / ürperdi / donakaldı_ tables, the repetition ban, chengyu handling, address rules, `[BELİRSİZ]`, `[ÖNERİ]`, and the DURUM NOTU format.

Verify it is present. If the system prompt does not contain the verb-selection tables of §4 and the syntax table of §2, **stop and say so** rather than translating from memory of them. A chapter translated without the core looks fine and is wrong in every paragraph, which is the expensive kind of wrong.

A copy is deliberately **not** bundled here: two copies drift, and the one in the system prompt is the one that persists across every turn of a long chapter.

## Inputs

- `<chapter_template>`: the Bölüm Açılış Şablonu for this chapter.
- `<chinese_raw>`: the Chinese source.
- `<english_ref>`: the English translation.

## Şablon sözleşmesi (contract with the template)

The template is not advisory. Its authority, section by section:

- **A** overrides every vocabulary instinct and every core default. A.1 is copied exactly; A.2 is used as given and never re-coined; **A.3 is a prohibition** — the listed names are not to appear, and the named "wrong term" is forbidden even where it feels natural.
- **B** is the load-bearing section. Frozen lines are byte-identical at every occurrence; synonym variation inside one chapter is an unrecoverable error.
- **C** governs voice. Where a Türkçe kadran is set (mood, pro-drop, particles, verbal register, izafet), it outranks your ear. **Kapalı siciller are hard bans.** Calibration lines are illustrative and never pasted into the output.
- **D** resolves the core's general address rules into concrete assignments. Do not recompute intimacy mid-scene.
- **E** carries the chapter-specific overrides, including budget allocation: spend heavy words where E says, and leave starved what E says to starve.

**Conflicts:** template beats core, because the core is general and the template is this chapter. **Exception:** the template may not license anything the core forbids outright — if it seems to, translate conservatively and flag `[BELİRSİZ]`.

**The English map can be revoked.** The core lets you use the English for entity positioning. When E reports a paragraph misalignment, the English is void from that paragraph onward: follow the Chinese sequence alone, including paragraph boundaries and dialogue-tag line breaks. Where the template reports an English mistranslation, translate the Chinese and do not smooth toward the English reading.

**If no template is supplied**, say so before starting: terms, frozen lines and voice calibration will be improvised and the chapter will need heavier review.

## Chunking

Chapters arrive in parts. At each part: re-read the template's C and E for the characters present, then translate. Emit the DURUM NOTU block after each part per the core's §9 format — its purpose is to keep spent heavy words and perception verbs visible across chunk boundaries, where drift actually happens.

## Output

Only the finished Turkish, as clean Markdown. No Chinese, no English, no `¶` markers, no comparison headers. Inner monologue in italics, not quotation marks. Then the DURUM NOTU block.
