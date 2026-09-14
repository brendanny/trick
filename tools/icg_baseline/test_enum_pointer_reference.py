"""Apply the immutable reference protocol to the enum pointer corpus."""

from pathlib import Path

import test_enum_reference


class EnumPointerReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("enum_pointers")
