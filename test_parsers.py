"""Parser tests for Aibis Lead Engine."""
import re
from exporter import clean_phone_number
from database import normalize_text

def test_normalize_text():
    """Normalisasi case-insensitive, hapus simbol, kompres spasi."""
    assert normalize_text("  Kopi Kenangan  ") == "kopi kenangan"
    assert normalize_text("Kopi-Kenangan!@#") == "kopikenangan"
    assert normalize_text("Kopi   Kenangan") == "kopi kenangan"
    assert normalize_text("") == ""
    assert normalize_text(None) == ""

def test_clean_phone_number():
    """Phone cleaning Indonesia: 08xx -> 628xx, +62xx -> 62xx."""
    phone, wa = clean_phone_number("0812-3456-7890")
    assert phone == "0812-3456-7890"
    assert wa == "https://wa.me/6281234567890"

    phone, wa = clean_phone_number("+62 812 3456 7890")
    assert wa == "https://wa.me/6281234567890"

    phone, wa = clean_phone_number("6281234567890")
    assert wa == "https://wa.me/6281234567890"

    phone, wa = clean_phone_number("")
    assert phone is None and wa is None

    phone, wa = clean_phone_number("123")
    assert wa is None

def test_rating_review_regex():
    """Regex rating/review Indonesia: 4,9(1.779) -> 4.9, 1779."""
    pattern = re.compile(r"(\d+[\.,]\d+)\((\d+[\.,]?\d*)\)")

    m = pattern.search("4,9(1.779)")
    assert m
    assert float(m.group(1).replace(",", ".")) == 4.9
    assert int(m.group(2).replace(".", "")) == 1779

    m = pattern.search("4.8(556)")
    assert m
    assert float(m.group(1)) == 4.8
    assert int(m.group(2)) == 556

    m = pattern.search("5,0(10)")
    assert m
    assert float(m.group(1).replace(",", ".")) == 5.0
    assert int(m.group(2)) == 10

    m = pattern.search("Buka · Kedai Kopi")
    assert m is None

if __name__ == "__main__":
    test_normalize_text()
    test_clean_phone_number()
    test_rating_review_regex()
    print("All parser tests passed!")
