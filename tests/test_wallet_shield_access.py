"""WalletShield v0.2 community privacy and specialist/legal authorization gates."""
import unittest

from core.wallet_shield_access import (
    Action, AccessRequest, Principal, REQUIREMENTS, check_access,
    passive_community_settings,
)

NOW = 1_000_000
REFS = {name: "opaque_attestation_abcdefghij_" + str(index)
        for index, name in enumerate({
            requirement for _, requirements in REQUIREMENTS.values()
            for requirement in requirements
        })}


def request(
    action=Action.AUTHORITY_EVIDENCE_DISCLOSURE,
    principal=Principal.LEGAL_AUTHORITY,
    credential_names=(),
    case_id="case_12345",
    expires=NOW + 300,
):
    return AccessRequest(
        action=action,
        principal=principal,
        case_id=case_id,
        attestations={k: REFS[k] for k in credential_names},
        session_expires_at=expires,
    )


class Verifier:
    def __init__(self, denied=(), fail=False):
        self.denied = frozenset(denied)
        self.fail = fail
        self.calls = []

    def verify(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("verification backend offline")
        return kwargs["attestation_type"] not in self.denied


class PrivacyTests(unittest.TestCase):
    def test_default_settings_have_no_remote_observation(self):
        settings = passive_community_settings()
        self.assertTrue(settings["local_on_device_advisories"])
        for name, value in settings.items():
            if name != "local_on_device_advisories":
                self.assertIs(value, False, name)

    def test_no_verifier_denies_even_complete_attestations(self):
        required = REQUIREMENTS[Action.AUTHORITY_EVIDENCE_DISCLOSURE][1]
        decision = check_access(request(credential_names=required), at_utc=NOW)
        self.assertFalse(decision.eligible_for_separate_authorization)
        self.assertEqual("trusted_verifier_unavailable", decision.code)

    def test_judge_authorization_and_victim_consent_both_required(self):
        all_names = REQUIREMENTS[Action.AUTHORITY_EVIDENCE_DISCLOSURE][1]
        for missing in ("court_order", "judge_authorization", "victim_consent"):
            with self.subTest(missing=missing):
                other = tuple(name for name in all_names if name != missing)
                decision = check_access(request(credential_names=other), Verifier(), at_utc=NOW)
                self.assertFalse(decision.eligible_for_separate_authorization)
                self.assertIn(missing, decision.missing_requirements)

    def test_self_declared_credential_does_not_pass_verifier(self):
        all_names = REQUIREMENTS[Action.AUTHORITY_EVIDENCE_DISCLOSURE][1]
        verifier = Verifier(denied=("victim_consent",))
        decision = check_access(request(credential_names=all_names), verifier, at_utc=NOW)
        self.assertFalse(decision.eligible_for_separate_authorization)
        self.assertIn("victim_consent", decision.missing_requirements)

    def test_case_role_and_session_expiry_are_enforced(self):
        all_names = REQUIREMENTS[Action.AUTHORITY_EVIDENCE_DISCLOSURE][1]
        self.assertEqual("role_mismatch", check_access(
            request(principal=Principal.SPECIALIST, credential_names=all_names),
            Verifier(), at_utc=NOW,
        ).code)
        self.assertEqual("session_expired_or_too_long", check_access(
            request(expires=NOW - 1, credential_names=all_names),
            Verifier(), at_utc=NOW,
        ).code)
        self.assertEqual("session_expired_or_too_long", check_access(
            request(expires=NOW + 3601, credential_names=all_names),
            Verifier(), at_utc=NOW,
        ).code)

    def test_authority_even_all_verified_only_preflight_not_access(self):
        all_names = REQUIREMENTS[Action.AUTHORITY_EVIDENCE_DISCLOSURE][1]
        verifier = Verifier()
        decision = check_access(request(credential_names=all_names), verifier, at_utc=NOW)
        self.assertTrue(decision.eligible_for_separate_authorization)
        self.assertFalse(decision.data_retrieved)
        self.assertFalse(decision.outbound_sent)
        self.assertEqual(set(all_names), {c["attestation_type"] for c in verifier.calls})
        self.assertTrue(all(c["case_id"] == "case_12345" for c in verifier.calls))
        self.assertTrue(all(c["action"] is Action.AUTHORITY_EVIDENCE_DISCLOSURE for c in verifier.calls))

    def test_specialist_needs_owner_consent_and_assignment(self):
        names = REQUIREMENTS[Action.SPECIALIST_REVIEW][1]
        decision = check_access(request(
            action=Action.SPECIALIST_REVIEW, principal=Principal.SPECIALIST,
            credential_names=("specialist_role", "case_assignment"),
        ), Verifier(), at_utc=NOW)
        self.assertIn("victim_consent", decision.missing_requirements)
        decision = check_access(request(
            action=Action.SPECIALIST_REVIEW, principal=Principal.SPECIALIST,
            credential_names=names,
        ), Verifier(), at_utc=NOW)
        self.assertTrue(decision.eligible_for_separate_authorization)

    def test_recovery_guidance_has_same_scope_requirement(self):
        names = REQUIREMENTS[Action.SPECIALIST_RECOVERY_GUIDANCE][1]
        missing_consent = tuple(n for n in names if n != "victim_consent")
        result = check_access(request(
            action=Action.SPECIALIST_RECOVERY_GUIDANCE, principal=Principal.SPECIALIST,
            credential_names=missing_consent,
        ), Verifier(), at_utc=NOW)
        self.assertFalse(result.eligible_for_separate_authorization)

    def test_public_advisory_must_be_case_free_and_reviewed(self):
        names = REQUIREMENTS[Action.COMMUNITY_PUBLIC_ADVISORY][1]
        with self.assertRaises(ValueError):
            request(
                action=Action.COMMUNITY_PUBLIC_ADVISORY,
                principal=Principal.COMMUNITY_PUBLISHER, credential_names=names,
            )
        req = request(
            action=Action.COMMUNITY_PUBLIC_ADVISORY,
            principal=Principal.COMMUNITY_PUBLISHER,
            credential_names=names, case_id=None,
        )
        self.assertTrue(check_access(req, Verifier(), at_utc=NOW).eligible_for_separate_authorization)
        self.assertIn("public_only_attestation", check_access(
            request(action=Action.COMMUNITY_PUBLIC_ADVISORY,
                    principal=Principal.COMMUNITY_PUBLISHER, case_id=None,
                    credential_names=("publisher_role", "editorial_review")),
            Verifier(), at_utc=NOW,
        ).missing_requirements)

    def test_no_secret_fields_accepted(self):
        with self.assertRaises(ValueError):
            AccessRequest(
                action=Action.AUTHORITY_EVIDENCE_DISCLOSURE,
                principal=Principal.LEGAL_AUTHORITY,
                case_id="case_12345",
                attestations={"seed_phrase": "opaque_attestation_abcdefghijk"},
                session_expires_at=NOW + 300,
            )
        with self.assertRaises(ValueError):
            AccessRequest(
                action=Action.AUTHORITY_EVIDENCE_DISCLOSURE,
                principal=Principal.LEGAL_AUTHORITY,
                case_id="case_12345",
                attestations={"victim_consent": "true"},
                session_expires_at=NOW + 300,
            )

    def test_verification_unavailable_fails_closed(self):
        all_names = REQUIREMENTS[Action.AUTHORITY_EVIDENCE_DISCLOSURE][1]
        result = check_access(request(credential_names=all_names), Verifier(fail=True), at_utc=NOW)
        self.assertFalse(result.eligible_for_separate_authorization)


if __name__ == "__main__":
    unittest.main()
