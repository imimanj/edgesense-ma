import unittest

from shared.event_store import (
    event_matches_filters,
)


class EventCategoryFilterTests(unittest.TestCase):
    def setUp(self):
        self.person_event = {
            "final_risk": "LOW",
            "trigger_reason": "pir_motion",
            "detected_objects": ["person"],
            "primary_category": "person",
            "categories": ["person"],
        }

        self.unknown_event = {
            "final_risk": "LOW",
            "trigger_reason": "pir_motion",
            "detected_objects": [],
            "primary_category": "unknown_motion",
            "categories": ["unknown_motion"],
        }

    def test_person_category_matches(self):
        self.assertTrue(
            event_matches_filters(
                self.person_event,
                category="person",
            )
        )

    def test_unknown_motion_matches(self):
        self.assertTrue(
            event_matches_filters(
                self.unknown_event,
                category="unknown_motion",
            )
        )

    def test_wrong_category_does_not_match(self):
        self.assertFalse(
            event_matches_filters(
                self.person_event,
                category="animal",
            )
        )

    def test_category_filter_is_case_insensitive(self):
        self.assertTrue(
            event_matches_filters(
                self.person_event,
                category="PERSON",
            )
        )

    def test_all_category_disables_filter(self):
        self.assertTrue(
            event_matches_filters(
                self.person_event,
                category="All",
            )
        )


if __name__ == "__main__":
    unittest.main()
