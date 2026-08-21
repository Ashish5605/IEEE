from src import language


def test_default_language_is_english():
    assert language.DEFAULT_LANGUAGE == "en"
    assert language.detect_language("What is the attendance requirement?") == "en"


def test_resolve_always_returns_english():
    """The assistant answers in English regardless of what is requested."""
    assert language.resolve_language("auto", "What is the attendance requirement?") == "en"
    assert language.resolve_language("", "anything") == "en"
    assert language.resolve_language(None, "anything") == "en"


def test_language_name_lookup():
    assert language.language_name("en") == "English"
    assert language.language_name("zz") == "English"  # unknown falls back


def test_fixed_responses_exist():
    assert language.not_found_message()
    assert language.greeting_response()
    assert language.corpus_intro()
    assert language.corpus_empty()
