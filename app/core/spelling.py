"""Conservative local phrase suggestions. Never rewrite raw OCR or proper names globally."""
import re
import unicodedata

# Contextual phrases only: bare 'Minh', 'Ham', 'a', etc. are ambiguous.
PHRASES = {
    "minh mở sap": "mình mở sạp",
    "mở sap": "mở sạp",
    "ham nhớ": "hăm nhớ",
    "đến hen": "đến hẹn",
    "tiết kiệm chỉ phí": "tiết kiệm chi phí",
    "y là minh": "ý là mình",
    "học va làm": "học và làm",
    "bài bản vê": "bài bản về",
    "quán ăn nao": "quán ăn nào",
    "cảm on": "cảm ơn",
    "cám on": "cảm ơn",
    "xin lổi": "xin lỗi",
    "sử lý": "xử lý",
    "xãy ra": "xảy ra",
    "sẳn sàng": "sẵn sàng",
}


def suggest_spelling(text: str) -> tuple[str, list[str]]:
    result = unicodedata.normalize("NFC", text)
    changes = []
    for source, target in PHRASES.items():
        def replace(match):
            original = match.group()
            replacement = target.capitalize() if original[0].isupper() else target
            changes.append(f"{original} → {replacement}")
            return replacement
        result = re.sub(r"(?<![\w@./])" + re.escape(source) + r"(?![\w./])", replace, result, flags=re.IGNORECASE)
    return result, changes
