from src import language


def test_detects_english():
    assert language.detect_language("What is the attendance requirement?") == "en"


def test_detects_tamil():
    assert language.detect_language("குறைந்தபட்ச வருகைத் தேவை என்ன?") == "ta"


def test_detects_hindi():
    assert language.detect_language("न्यूनतम उपस्थिति की आवश्यकता क्या है?") == "hi"


def test_detect_handles_empty_and_none():
    assert language.detect_language("") == "en"
    assert language.detect_language(None) == "en"


def test_language_name_lookup():
    assert language.language_name("en") == "English"
    assert language.language_name("ta") == "Tamil"
    assert language.language_name("hi") == "Hindi"
    assert language.language_name("zz") == "English"  # unknown falls back


def test_auto_resolves_by_detection():
    assert language.resolve_language("auto", "What is the attendance requirement?") == "en"
    assert language.resolve_language("auto", "குறைந்தபட்ச வருகைத் தேவை என்ன?") == "ta"


def test_explicit_choice_overrides_detection():
    # User types in English but picked Tamil in the selector — selector wins.
    assert language.resolve_language("ta", "What is the attendance requirement?") == "ta"
    assert language.resolve_language("hi", "What is the attendance requirement?") == "hi"


def test_unknown_request_falls_back_to_detection():
    assert language.resolve_language("klingon", "न्यूनतम उपस्थिति क्या है?") == "hi"
    assert language.resolve_language(None, "Hello there") == "en"


def test_fixed_responses_are_localized():
    for code in ("en", "ta", "hi"):
        assert language.not_found_message(code)
        assert language.greeting_response(code)
    # Each language must actually differ — otherwise translation silently regressed.
    assert len({language.not_found_message(c) for c in ("en", "ta", "hi")}) == 3
    assert language.not_found_message("zz") == language.not_found_message("en")
