import unittest
from app.core.config import CleanerSettings
from app.core.text_cleaner import clean_text


class TextCleanerTests(unittest.TestCase):
    def test_emoticons(self):
        for suffix in ("=)))", "=))", "=)", "=(((", "=((", "=(", ":)))", ":))", ":)", ":((", ":(", "T_T", "^^", ":-)"):
            with self.subTest(suffix=suffix):
                self.assertEqual(clean_text("hello " + suffix), "hello")

    def test_vietnamese_and_punctuation(self):
        self.assertEqual(clean_text("buồn quá =(("), "buồn quá")
        self.assertEqual(clean_text("cái gì vậy????"), "cái gì vậy????")
        self.assertEqual(clean_text("Giá 5$ + 2 = 7; © tác giả"), "Giá 5$ + 2 = 7; © tác giả")
        self.assertEqual(clean_text("f(x)=((x+1))"), "f(x)=((x+1))")

    def test_url_configuration(self):
        self.assertEqual(clean_text("hello https://example.com"), "hello")
        self.assertEqual(clean_text("hello https://example.com", CleanerSettings(remove_urls=False)), "hello https://example.com")
        self.assertEqual(clean_text("Xem https://example.com. Tiếp nhé!"), "Xem . Tiếp nhé!")

    def test_emoji_configuration(self):
        self.assertEqual(clean_text("Vui 😂 👨‍👩‍👧‍👦 1️⃣"), "Vui")
        self.assertEqual(clean_text("Vui 😂", CleanerSettings(emoji_mode="keep")), "Vui 😂")
        with self.assertRaises(ValueError):
            clean_text("Vui", CleanerSettings(emoji_mode="meaning"))

    def test_conservative_username(self):
        self.assertEqual(clean_text("@linh nói hay"), "@linh nói hay")
        self.assertEqual(clean_text("@linh nói hay", username="linh"), "nói hay")
        self.assertEqual(clean_text("linhchi nói hay", username="linh"), "linhchi nói hay")
        self.assertEqual(clean_text("@linh nói hay", CleanerSettings(read_username=True), "linh"), "@linh nói hay")

    def test_optional_emoticons_and_empty(self):
        self.assertEqual(clean_text("hello =)))", CleanerSettings(remove_emoticons=False)), "hello =)))")
        self.assertEqual(clean_text(" \n \t"), "")
