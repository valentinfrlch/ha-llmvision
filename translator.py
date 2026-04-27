import asyncio
import json
import os

from googletrans import Translator
from tqdm import tqdm

TRANSLATION_DIR = "custom_components/llmvision/translations/"
REFERENCE = "en.json"  # reference file to translate from
MISSING_ONLY = True  # if True, only translate keys that are missing in the target translation file

GENERATE_LANGUAGES = [
    "bg",
    "ca",
    # "zh-cn", # rename from cn to zh-cn
    "cs",
    "da",
    "de",
    "el",
    "fr",
    "hu",
    "it",
    "ja",
    "lt",
    "lv",
    "nl",
    "pl",
    "pt",
    "tr",
    "sk",
    "sl",
    "sv",
]


def load_reference_data():
    reference_path = os.path.join(TRANSLATION_DIR, REFERENCE)
    with open(reference_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_translation_file(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")


def count_strings(value):
    if isinstance(value, str):
        return 1
    elif isinstance(value, dict):
        return sum(count_strings(v) for v in value.values())
    elif isinstance(value, list):
        return sum(count_strings(item) for item in value)
    return 0


def get_missing(reference, existing):
    """Return the subset of reference whose keys are absent from existing."""
    if not isinstance(reference, dict):
        return reference
    missing = {}
    for k, v in reference.items():
        if k not in existing:
            missing[k] = v
        elif isinstance(v, dict) and isinstance(existing[k], dict):
            sub = get_missing(v, existing[k])
            if sub:
                missing[k] = sub
    return missing


def merge(existing, additions):
    """Merge additions into existing, recursing into shared dict keys."""
    if isinstance(existing, dict) and isinstance(additions, dict):
        result = dict(existing)
        for k, v in additions.items():
            result[k] = merge(result[k], v) if k in result and isinstance(result.get(k), dict) else v
        return result
    return additions


async def translate_file(reference_data, file_path, target_language, translator):
    if MISSING_ONLY and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        to_translate = get_missing(reference_data, existing_data)
    else:
        existing_data = {}
        to_translate = reference_data

    if not to_translate:
        print(f"{os.path.basename(file_path)}: nothing to translate")
        return

    total = count_strings(to_translate)
    with tqdm(total=total, desc=os.path.basename(file_path), unit="str") as bar:
        translated_additions = await translate_value(to_translate, target_language, translator, bar)

    write_translation_file(file_path, merge(existing_data, translated_additions))

async def translate_value(value, target_language, translator, bar):
    if isinstance(value, str):
        result = await translator.translate(value, dest=target_language)
        bar.update(1)
        return result.text
    elif isinstance(value, dict):
        translated = {}
        for k, v in value.items():
            translated[k] = await translate_value(v, target_language, translator, bar)
        return translated
    elif isinstance(value, list):
        return [await translate_value(item, target_language, translator, bar) for item in value]
    else:
        return value

async def main():
    async with Translator() as translator:
        reference_data = load_reference_data()
        os.makedirs(TRANSLATION_DIR, exist_ok=True)
        for lang in GENERATE_LANGUAGES:
            file_path = f"{TRANSLATION_DIR}{lang}.json"
            await translate_file(reference_data, file_path, lang, translator)


if __name__ == "__main__":
    asyncio.run(main())