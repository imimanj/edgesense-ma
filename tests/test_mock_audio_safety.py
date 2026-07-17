import unittest

from shared.decision_logic import score_audio


class MockAudioSafetyTests(unittest.TestCase):
    def test_mock_alarm_is_neutral(self):
        score, reason, summary = score_audio(
            event="alarm_like_sound",
            confidence=0.99,
            volume_db=99.0,
            source_mode="mock",
            hardware_ready=False,
        )

        self.assertEqual(score, 0)
        self.assertFalse(
            summary["trusted_for_risk"]
        )
        self.assertIn(
            "excluded from risk scoring",
            reason,
        )

    def test_mock_loud_noise_is_neutral(self):
        score, _, summary = score_audio(
            event="loud_noise",
            confidence=0.90,
            volume_db=80.0,
            source_mode="mock",
            hardware_ready=False,
        )

        self.assertEqual(score, 0)
        self.assertFalse(
            summary["trusted_for_risk"]
        )

    def test_unknown_audio_is_neutral(self):
        score, _, summary = score_audio(
            event="alarm_like_sound",
            confidence=0.90,
            volume_db=90.0,
        )

        self.assertEqual(score, 0)
        self.assertFalse(
            summary["trusted_for_risk"]
        )

    def test_ready_audio_can_raise_score(self):
        score, _, summary = score_audio(
            event="alarm_like_sound",
            confidence=0.90,
            volume_db=90.0,
            source_mode="real",
            hardware_ready=True,
        )

        self.assertEqual(score, 2)
        self.assertTrue(
            summary["trusted_for_risk"]
        )


if __name__ == "__main__":
    unittest.main()
