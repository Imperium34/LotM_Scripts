#!/usr/bin/env python3
"""
Glossary lookup for the translation project.

Searches two sources for a term (Turkish or English side, either direction):
  1. A YAML glossary where each entry has top-level terim/ingilizce, and may
     also have a `mertebeler` list whose `isim` field embeds a *second*
     translation pair inline as "Turkish (English)".
  2. A plain-text bullet list: "- **Turkish** — English"

Usage:
    translation_lookup.py <query>
    translation_lookup.py --notes <query>   # also print cevirmen_notu text
"""

import re
import sys
import yaml
from pathlib import Path

YAML_PATH = Path.home() / "Projects/LotM/Imperium34.github.io/_data/sozluk.yml"
TEXT_PATH = Path.home() / "Projects/LotM/Tools/words.md"

# Matches "Something (Something Else)" — used to split isim's embedded pair.
ISIM_PATTERN = re.compile(r"^(.*?)\s*\((.*?)\)\s*$")
# Matches "- **Turkish** — English" (also tolerates a plain "-" hyphen instead of an em dash)
BULLET_PATTERN = re.compile(r"^\s*-\s*\*\*(.+?)\*\*\s*[—-]\s*(.+?)\s*$")


class Entry:
    __slots__ = ("turkish", "english", "source", "context", "note")

    def __init__(self, turkish, english, source, context, note=None):
        self.turkish = turkish
        self.english = english
        self.source = source  # "yaml:top" / "yaml:mertebe" / "text"
        self.context = context  # human-readable location, e.g. parent term / kategori
        self.note = note  # cevirmen_notu, if any

    def matches(self, query):
        q = query.lower()
        return q in self.turkish.lower() or q in self.english.lower()

    def display(self, show_notes=False):
        line = f"  {self.turkish}  →  {self.english}"
        line += f"   [{self.context}]"
        out = [line]
        if show_notes and self.note:
            out.append(f"    note: {self.note}")
        return "\n".join(out)


def load_yaml_entries(path):
    if not path.exists():
        print(f"warning: yaml glossary not found at {path}", file=sys.stderr)
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    entries = []
    for item in data:
        terim = item.get("terim")
        ingilizce = item.get("ingilizce")
        kategori = item.get("kategori", "")

        if terim and ingilizce:
            entries.append(
                Entry(
                    turkish=terim,
                    english=ingilizce,
                    source="yaml:top",
                    context=kategori or "top-level",
                    note=item.get("cevirmen_notu"),
                )
            )

        for mertebe in item.get("mertebeler", []) or []:
            isim = mertebe.get("isim", "")
            match = ISIM_PATTERN.match(isim)
            if not match:
                continue
            tr, en = match.group(1).strip(), match.group(2).strip()
            level = mertebe.get("seviye", "?")
            entries.append(
                Entry(
                    turkish=tr,
                    english=en,
                    source="yaml:mertebe",
                    context=f"{terim} — seviye {level}",
                    note=mertebe.get("cevirmen_notu"),
                )
            )

    return entries


def load_text_entries(path):
    if not path.exists():
        print(f"warning: text list not found at {path}", file=sys.stderr)
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            match = BULLET_PATTERN.match(line)
            if not match:
                continue
            tr, en = match.group(1).strip(), match.group(2).strip()
            entries.append(Entry(tr, en, source="text", context="simple list"))

    return entries


def search(entries, query):
    return [e for e in entries if e.matches(query)]


def main():
    args = sys.argv[1:]
    show_notes = False
    if "--notes" in args:
        show_notes = True
        args.remove("--notes")

    if not args:
        print("usage: translation_lookup.py [--notes] <query>", file=sys.stderr)
        sys.exit(1)

    query = " ".join(args)

    entries = load_yaml_entries(YAML_PATH) + load_text_entries(TEXT_PATH)
    results = search(entries, query)

    if not results:
        print(f"No matches for '{query}'.")
        return

    print(f"{len(results)} match(es) for '{query}':\n")
    for entry in results:
        print(entry.display(show_notes=show_notes))
        print()


if __name__ == "__main__":
    main()
