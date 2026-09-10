"""Conservative, deterministic rules; no OCR guessing or AI calls."""
import logging
import re
from app.core.config import CleanerSettings

log = logging.getLogger(__name__)
EMOTICONS = re.compile(r"[=:;][\-']?(?:\)+|\(+)(?![\w(])|(?<!\w)[Tt]_[Tt](?!\w)|\^{2,}")
URL = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0E\uFE0F\u200D\U000E0020-\U000E007F]"
)
KEYCAP = re.compile("[#*0-9]\ufe0f?\u20e3")


def clean_text(text: str, settings: CleanerSettings | None = None, username: str = "") -> str:
    settings = settings or CleanerSettings()
    if settings.emoji_mode not in {"ignore", "keep"}:
        raise ValueError("Emoji meaning mode is not implemented; choose ignore or keep.")
    if settings.remove_emoticons:
        text = EMOTICONS.sub("", text)
    if settings.remove_urls:
        # Preserve sentence punctuation following a URL.
        text = URL.sub(lambda match: match.group()[len(match.group().rstrip(".,!?;:")):], text)
    if not settings.read_username and username:
        text = re.sub(r"(?<!\w)@?" + re.escape(username.lstrip("@")) + r"(?!\w)", "", text)
    if settings.emoji_mode == "ignore":
        text = EMOJI.sub("", KEYCAP.sub("", text))
    log.info("Text cleaned")
    return " ".join(text.split())
