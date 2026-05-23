import unittest

from chroma_db import vector_id_for_job
from service.analytics_service import get_area_distribution, get_top_skills
from service.job_service import JobService
from service.storage_adapter import split_tags
from utilities import extract_chroma_entry, sort_jobs_by_fitness


class CoreBehaviorTests(unittest.TestCase):
    def test_normalize_job_preserves_existing_source(self):
        job = JobService.normalize_job(
            {"id": 123, "source": "RemoteOK", "title": "ML Engineer", "tags": ["Python", "NLP"]},
            source="fallback",
        )

        self.assertEqual(job["id"], "123")
        self.assertEqual(job["source"], "RemoteOK")
        self.assertEqual(job["tags"], "Python, NLP")

    def test_extract_chroma_entry_flattens_chroma_shape(self):
        rows = extract_chroma_entry(
            {
                "ids": [["RemoteOK:1", "RemoteOK:2"]],
                "metadatas": [[{"id": "1", "title": "A"}, {"id": "2", "title": "B"}]],
                "distances": [[0.3, 2.0]],
            }
        )

        self.assertEqual(
            rows,
            [
                {
                    "id": "1",
                    "title": "A",
                    "vector_id": "RemoteOK:1",
                    "distance": 0.3,
                    "company": "N/A",
                    "url": "N/A",
                    "link": "N/A",
                }
            ],
        )

    def test_extract_chroma_entry_accepts_legacy_results_shape(self):
        rows = extract_chroma_entry({"results": [{"id": "1", "title": "A"}]})

        self.assertEqual(rows, [{"id": "1", "title": "A"}])

    def test_vector_id_includes_source(self):
        self.assertEqual(vector_id_for_job({"id": "42", "source": "JSearch"}), "JSearch:42")

    def test_split_tags_handles_strings_lists_and_na(self):
        self.assertEqual(split_tags("Python, NLP"), ["Python", "NLP"])
        self.assertEqual(split_tags(["Python", " NLP "]), ["Python", "NLP"])
        self.assertEqual(split_tags("N/A"), [])

    def test_analytics_helpers_are_dependency_light(self):
        jobs = [{"title": "NLP Engineer", "description": "Transformers with pandas", "tags": "Python, NLP"}]

        self.assertEqual(get_area_distribution(jobs), [{"category": "NLP", "count": 1}])
        self.assertEqual(get_top_skills(jobs, n=2), [{"value": "Python", "count": 1}, {"value": "NLP", "count": 1}])

    def test_sort_jobs_by_fitness_orders_by_fitness(self):
        jobs = [
            {"title": "Senior ML Engineer", "job_fitness": "9", "distance": 0.2},
            {"title": "Junior ML Engineer", "job_fitness": "7", "distance": 0.4},
            {"title": "ML Intern", "job_fitness": "8", "distance": 0.6},
        ]

        sorted_jobs = sort_jobs_by_fitness(jobs)

        self.assertEqual([job["title"] for job in sorted_jobs], ["Senior ML Engineer", "ML Intern", "Junior ML Engineer"])


if __name__ == "__main__":
    unittest.main()
