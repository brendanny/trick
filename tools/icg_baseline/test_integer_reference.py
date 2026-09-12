"""Apply the immutable reference protocol to the separate integer corpus."""

from pathlib import Path

import test_enum_reference


class IntegerReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("integers")
