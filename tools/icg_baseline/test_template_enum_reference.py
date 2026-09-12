"""Apply the immutable reference protocol to the enum-template corpus."""

from pathlib import Path

import test_enum_reference


class TemplateEnumReferenceTests(test_enum_reference.EnumReferenceTests):
    HERE = Path(__file__).with_name("template_enums")
