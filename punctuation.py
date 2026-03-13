import re

PUNCTUATION_MAP = [
    (r"\bfrågetecken\b", "?"),
    (r"\butropstecken\b", "!"),
    (r"\bkommatecken\b", ","),
    (r"\bsemikolon\b", ";"),
    (r"\btre punkter\b", "..."),
    (r"\bellips\b", "..."),
    (r"\bny rad\b", "\n"),
    (r"\bnyrad\b", "\n"),
    (r"\bcitattecken\b", '"'),
]


def smart_punctuation(text):
    result = text
    for pattern, symbol in PUNCTUATION_MAP:
        result = re.sub(pattern, symbol, result, flags=re.IGNORECASE)
    # Clean spaces before standard punctuation
    result = re.sub(r"\s+([?.!,;:])", r"\1", result)
    # Clean spaces around newlines
    result = re.sub(r" *\n *", "\n", result)
    # Clean spaces inside quote pairs: remove space after opening " and before closing "
    result = re.sub(r'" (.*?) "', r'"\1"', result)
    result = re.sub(r'"(.*?) "', r'"\1"', result)
    return result
