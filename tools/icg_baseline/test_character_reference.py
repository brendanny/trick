"""Apply the immutable reference protocol to the separate character corpus."""

from pathlib import Path

import test_enum_reference


class CharacterReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("characters")
