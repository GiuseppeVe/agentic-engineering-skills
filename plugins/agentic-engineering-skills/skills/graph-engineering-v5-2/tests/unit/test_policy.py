from __future__ import annotations

import unittest

from scripts.graph_v5.policy import (
    EgressPolicy,
    EvidenceRedactionPolicy,
    PolicyError,
    RedactingEvidenceWriter,
)


class PolicyTests(unittest.TestCase):
    def test_real_egress_requires_enforcement_receipt(self) -> None:
        with self.assertRaisesRegex(PolicyError, "egress gate"):
            EgressPolicy(
                hosts=("api.example.test",), enforcement_receipt=None
            ).admit()

    def test_unredactable_sensitive_output_fails_before_receipt(self) -> None:
        writer = RedactingEvidenceWriter(
            EvidenceRedactionPolicy(redaction_policy_digest="b" * 64)
        )

        with self.assertRaisesRegex(PolicyError, "redaction"):
            writer.write(b"token=unredactable")

    def test_known_sensitive_value_is_redacted_and_receipt_binds_policy(self) -> None:
        writer = RedactingEvidenceWriter(
            EvidenceRedactionPolicy(
                redaction_policy_digest="c" * 64,
            )
        )

        evidence = writer.write(
            b"token=sensitive-value",
            secret_values=(b"sensitive-value",),
        )

        self.assertEqual(evidence.payload, b"token=")
        self.assertEqual(evidence.receipt.policy_digest, "c" * 64)
        self.assertNotIn(b"sensitive-value", evidence.payload)
        self.assertNotIn("sensitive-value", repr(evidence.receipt))

    def test_encoded_secret_representations_are_redacted(self) -> None:
        writer = RedactingEvidenceWriter(
            EvidenceRedactionPolicy(redaction_policy_digest="a" * 64)
        )
        for secret, representation in (
            (b"secret!", b"c2VjcmV0IQ"),
            (b"\xfb\xff", b"-_8"),
            (b"\xab\xcd\xef", b"ABCDEF"),
        ):
            with self.subTest(representation=representation):
                evidence = writer.write(
                    b"result=" + representation,
                    secret_values=(secret,),
                )

                self.assertNotIn(representation, evidence.payload)

    def test_redaction_marker_cannot_reintroduce_secret_bytes(self) -> None:
        writer = RedactingEvidenceWriter(
            EvidenceRedactionPolicy(redaction_policy_digest="f" * 64)
        )

        evidence = writer.write(b"token=RED", secret_values=(b"RED",))

        self.assertNotIn(b"RED", evidence.payload)

    def test_redaction_policy_never_retains_resolved_secret_values(self) -> None:
        policy = EvidenceRedactionPolicy(redaction_policy_digest="d" * 64)

        self.assertFalse(hasattr(policy, "secret_values"))

    def test_unlabelled_bearer_token_requires_known_secret_coverage(self) -> None:
        writer = RedactingEvidenceWriter(
            EvidenceRedactionPolicy(redaction_policy_digest="e" * 64)
        )

        with self.assertRaisesRegex(PolicyError, "redaction"):
            writer.write(b"Bearer unredactable")


if __name__ == "__main__":
    unittest.main()
