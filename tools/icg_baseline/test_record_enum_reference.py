"""Apply the immutable reference protocol to the ordinary enum field corpus."""

from pathlib import Path

import test_enum_reference


class RecordEnumReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("record_enums")
