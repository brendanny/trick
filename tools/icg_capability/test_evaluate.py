import copy
import unittest

import evaluate


class EvaluateTests(unittest.TestCase):
    def document(self):
        observations = dict(evaluate.EXPECTED)
        observations["diamond_own_offset"] = 224
        return {
            "schema_version": 1,
            "frontend": {"api": "libclang-c", "version": "clang version 17.0.6"},
            "observations": observations,
        }

    def test_expected_results_select_libtooling_with_three_blockers(self):
        result = evaluate.evaluate(self.document())
        self.assertEqual(result["decision"], "libtooling")
        self.assertEqual(
            result["blockers"],
            ["base_layout", "implicit_special_members", "variadic_pack_elements"],
        )

    def test_probe_drift_fails_instead_of_changing_the_decision_silently(self):
        for mutation in (
            lambda value: value["observations"].update(base_specifiers=3),
            lambda value: value["observations"].update(diamond_own_offset=-1),
            lambda value: value.update(schema_version=2),
            lambda value: value["frontend"].update(version="clang version 18.0.0"),
        ):
            document = copy.deepcopy(self.document())
            mutation(document)
            with self.assertRaises(ValueError):
                evaluate.evaluate(document)

    def test_stable_view_ignores_package_text_and_target_field_offset(self):
        first = evaluate.evaluate(self.document())
        second = copy.deepcopy(first)
        second["frontend"]["version"] = "Debian clang version 17.0.6"
        second["observations"]["diamond_own_offset"] = 192
        self.assertEqual(evaluate.stable_view(first), evaluate.stable_view(second))


if __name__ == "__main__":
    unittest.main()
