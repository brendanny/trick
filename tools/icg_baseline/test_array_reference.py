"""Apply the immutable reference protocol to the separate array corpus."""

from pathlib import Path

import test_enum_reference


class ArrayReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("arrays")
