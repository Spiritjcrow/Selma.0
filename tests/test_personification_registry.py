import copy, json, unittest
from pathlib import Path
from tools.validate_personifications import canonical_digest, validate

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "personifications/fixtures/selma.synthetic.v1.json").read_text())
MAPPING = json.loads((ROOT / "personifications/renderers/reference.2d.v1.json").read_text())

class RegistryContractTests(unittest.TestCase):
    def test_fixture_is_valid_and_deterministic(self):
        self.assertEqual([], validate(RECORD, MAPPING))
        self.assertEqual(canonical_digest(RECORD), canonical_digest(json.loads(json.dumps(RECORD))))

    def test_classifications_are_never_collapsed(self):
        bad = copy.deepcopy(RECORD); del bad["classification"]["inferred_preferences"]
        self.assertIn("classification.inferred_preferences must be explicit", validate(bad, MAPPING))

    def test_unknown_provenance_fails(self):
        bad = copy.deepcopy(RECORD); bad["classification"]["authored_design"][0]["source_id"] = "missing"
        self.assertIn("unknown source_id in authored_design", validate(bad, MAPPING))

    def test_living_subject_requires_authorization(self):
        bad = copy.deepcopy(RECORD); bad["classification"]["identity_basis"] = "authorized-subject"
        self.assertIn("authorized subjects require documented likeness and voice authorization", validate(bad, MAPPING))

    def test_renderer_must_cover_contract(self):
        bad = copy.deepcopy(MAPPING); del bad["states"]["ERROR"]
        self.assertIn("renderer mapping does not cover every state", validate(RECORD, bad))

    def test_sensitive_dataset_fields_fail(self):
        bad = copy.deepcopy(RECORD); bad["medical_data"] = "must never be present"
        self.assertIn("forbidden dataset field: medical_data", validate(bad, MAPPING))

if __name__ == "__main__": unittest.main()
