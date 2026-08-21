import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import language


def test_detects_english():
    assert language.detect_language("What is the attendance requirement?") == "en"


def test_detects_tamil():
    assert language.detect_language("குறைந்தபட்ச வருகைத் தேவை என்ன?") == "ta"


def test_detects_hindi():
    assert language.detect_language("न्यूनतम उपस्थिति की आवश्यकता क्या है?") == "hi"


def test_language_name_lookup():
    assert language.language_name("en") == "English"
    assert language.language_name("ta") == "Tamil"
    assert language.language_name("hi") == "Hindi"
