"""Apply the immutable reference protocol to the double pointer corpus."""

from pathlib import Path

import test_enum_reference


class DoublePointerReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("double_pointers")
