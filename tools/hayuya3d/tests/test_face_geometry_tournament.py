from __future__ import annotations

import unittest

from tools.hayuya3d.face_geometry_tournament import _rank_eligible


class FaceGeometryTournamentRankingTests(unittest.TestCase):
    def test_dreamsim_breaks_landmark_only_preference_after_hard_gates(self):
        rows=[
            {
                "name":"multiview_base",
                "median_profile_error":0.050,
                "p90_profile_error":0.070,
                "dreamsim_face_median_distance":0.420,
            },
            {
                "name":"source_face_challenger",
                "median_profile_error":0.060,
                "p90_profile_error":0.080,
                "dreamsim_face_median_distance":0.210,
            },
        ]
        ranked=_rank_eligible(rows,True)
        self.assertEqual(ranked[0]["name"],"source_face_challenger")

    def test_missing_dreamsim_for_any_eligible_candidate_falls_back_to_landmarks(self):
        rows=[
            {
                "name":"multiview_base",
                "median_profile_error":0.050,
                "p90_profile_error":0.070,
                "dreamsim_face_median_distance":0.420,
            },
            {
                "name":"source_face_challenger",
                "median_profile_error":0.060,
                "p90_profile_error":0.080,
            },
        ]
        ranked=_rank_eligible(rows,True)
        self.assertEqual(ranked[0]["name"],"multiview_base")

    def test_exact_geometry_tie_prefers_untouched_baseline(self):
        rows=[
            {
                "name":"source_face_challenger",
                "median_profile_error":0.050,
                "p90_profile_error":0.070,
            },
            {
                "name":"multiview_base",
                "median_profile_error":0.050,
                "p90_profile_error":0.070,
            },
        ]
        ranked=_rank_eligible(rows,False)
        self.assertEqual(ranked[0]["name"],"multiview_base")


if __name__=="__main__":
    unittest.main()
