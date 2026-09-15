"""Apply the immutable reference protocol to the record pointer corpus."""

from pathlib import Path

import test_enum_reference


class RecordPointerReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("record_pointers")
