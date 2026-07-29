import sys
import re

# python chinese_lookup.py ../Source/Lord_of_the_Mysteries_Chinese.txt <chapter_number>


def get_chapter(filepath, target_chapter):
    # Try reading as UTF-8 first, fallback to GBK if it fails
    try:
        file = open(filepath, "r", encoding="utf-8")
        file.readline()  # Test read
        file.seek(0)  # Reset to start
    except UnicodeDecodeError:
        file = open(filepath, "r", encoding="gbk")

    # Regex to detect lines starting with "第 [Chinese or Arabic numbers] 章"
    chapter_pattern = re.compile(r"^\s*第[一二三四五六七八九十百千零0-9]+章")

    current_chapter = 0
    printing = False

    for line in file:
        if chapter_pattern.match(line):
            current_chapter += 1

            # If we hit the chapter we want, start printing
            if current_chapter == target_chapter:
                printing = True
            # If we hit the NEXT chapter, stop entirely
            elif current_chapter > target_chapter:
                break

        if printing:
            # Print the line without adding double spaces
            print(line, end="")

    file.close()

    if not printing:
        print(
            f"Chapter {target_chapter} not found. The file only has {current_chapter} chapters."
        )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python read_chapter.py <file.txt> <chapter_number>")
        sys.exit(1)

    filepath = sys.argv[1]
    try:
        chapter_num = int(sys.argv[2])
        get_chapter(filepath, chapter_num)
    except ValueError:
        print("Error: The chapter number must be an integer (e.g., 28)")
