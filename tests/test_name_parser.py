from core.name_parser import extract_name


def test_extract_name_drops_trailing_intent_phrase():
    text = "I am chandrasekhar. Looking for DL appointment."
    assert extract_name(text) == "chandrasekhar"


def test_extract_name_simple_full_name():
    text = "my name is Mary Jane Watson"
    assert extract_name(text) == "Mary Jane Watson"


def test_extract_name_short_reply():
    assert extract_name("Alex") == "Alex"


def test_extract_name_ignores_hello():
    assert extract_name("hello") is None


def test_extract_name_ignores_intent_phrase():
    assert extract_name("looking for DL") is None


def test_extract_name_ignores_identity_phrase_with_article():
    assert extract_name("I am an international student") is None


def test_extract_name_ignores_identity_phrase_without_article():
    assert extract_name("I am international student") is None


def test_extract_name_keeps_valid_short_name_an():
    assert extract_name("An") == "An"
