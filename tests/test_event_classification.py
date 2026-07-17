import unittest

from shared.event_classification import (
    classify_event_objects,
)


class EventClassificationTests(
    unittest.TestCase
):
    def test_unknown_pir_motion(self):
        result = classify_event_objects(
            [],
            "pir_motion",
        )

        self.assertEqual(
            result["status"],
            "unclassified",
        )
        self.assertEqual(
            result["primary_category"],
            "unknown_motion",
        )
        self.assertTrue(
            result["motion_confirmed"]
        )

    def test_person(self):
        result = classify_event_objects(
            [
                {
                    "label": "person",
                    "confidence": 0.85,
                }
            ],
            "pir_motion",
        )

        self.assertEqual(
            result["primary_category"],
            "person",
        )
        self.assertEqual(
            result["categories"],
            ["person"],
        )

    def test_animal(self):
        result = classify_event_objects(
            [
                {
                    "label": "dog",
                    "confidence": 0.73,
                }
            ],
            "pir_motion",
        )

        self.assertEqual(
            result["primary_category"],
            "animal",
        )

    def test_vehicle(self):
        result = classify_event_objects(
            [
                {
                    "label": "bicycle",
                    "confidence": 0.68,
                }
            ],
            "pir_motion",
        )

        self.assertEqual(
            result["primary_category"],
            "vehicle",
        )

    def test_person_with_bag(self):
        result = classify_event_objects(
            [
                {
                    "label": "backpack",
                    "confidence": 0.64,
                },
                {
                    "label": "person",
                    "confidence": 0.91,
                },
            ],
            "pir_motion",
        )

        self.assertEqual(
            result["primary_category"],
            "person",
        )
        self.assertEqual(
            result["categories"],
            [
                "person",
                "carried_object",
            ],
        )

    def test_general_object(self):
        result = classify_event_objects(
            [
                {
                    "label": "chair",
                    "confidence": 0.55,
                }
            ],
            "pir_motion",
        )

        self.assertEqual(
            result["primary_category"],
            "general_object",
        )


if __name__ == "__main__":
    unittest.main()
