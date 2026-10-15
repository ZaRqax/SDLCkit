import unittest

from sdlc.workflows import condition, readiness, validate_recipe


class WorkflowTests(unittest.TestCase):
    def test_finite_conditions_and_optional_dependencies(self):
        context = {"task": {"complexity": "trivial", "high_risk": False}, "policy": {"requires_review": True}}
        self.assertFalse(condition("nontrivial", context))
        self.assertTrue(condition("requires_review", context))
        self.assertFalse(condition("task.complexity != 'trivial'", context))
        self.assertTrue(condition({"field": "task.complexity", "in": ["trivial", "standard"]}, context))
        self.assertEqual(readiness(["design?"], {"design": "skipped"}), "ready")
        self.assertEqual(readiness(["verify?"], {"verify": "failed"}), "blocked")
        self.assertEqual(readiness(["verify"], {"verify": "skipped"}), "blocked")
        self.assertEqual(readiness(["verify"], {"verify": "running"}), "pending")

    def test_rejects_arbitrary_expressions_cycles_missing_dependencies(self):
        for rule in ["__import__('os').system('false')", "task.unknown", {"field": "task.complexity", "eval": "x"}]:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                condition(rule, {})
        for stages in [[{"id": "x", "needs": ["y"]}],
                       [{"id": "x", "needs": ["y"]}, {"id": "y", "needs": ["x"]}],
                       [{"id": "x"}, {"id": "x"}]]:
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                validate_recipe({"stages": stages})


if __name__ == "__main__":
    unittest.main()
