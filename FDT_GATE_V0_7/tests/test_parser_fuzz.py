import random
import string
import unittest

from fdt_gate.language import tokenize_preserving_atomic_forms
from fdt_gate.policy import parse_policy


class ParserFuzzTests(unittest.TestCase):
    def test_atomic_forms_never_split(self):
        forms = ["\"jargonsaurousflex\" '`×π", "Table_Sãurāzz'd ållôt.."]
        for f in forms:
            tokens = tokenize_preserving_atomic_forms("prefix " + f + " suffix")
            self.assertIn(f, [t.text for t in tokens if t.kind == "ATOMIC_FORM"])

    def test_random_garbage_never_silently_compiles(self):
        rng = random.Random(0xF07)
        alphabet = string.ascii_letters + string.digits + " =-_!@#$%^&*"
        for _ in range(500):
            src = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 120)))
            try:
                result = parse_policy(src)
                self.assertTrue(result[0])
            except (ValueError, KeyError):
                pass


if __name__ == "__main__": unittest.main()
