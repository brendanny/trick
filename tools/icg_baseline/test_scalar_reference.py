"""Apply the immutable reference protocol to the separate scalar corpus."""

from pathlib import Path

import test_enum_reference


class ScalarReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("scalars")
