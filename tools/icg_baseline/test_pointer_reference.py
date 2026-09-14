"""Apply the immutable reference protocol to pointers and rejected references."""

from pathlib import Path

import test_enum_reference


class PointerReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("pointers")
