import json
from datetime import datetime
from pathlib import Path
from config import load_config
from filtering.resume_filter import evaluate_job, experience_requirements, skills_in, rank_jobs
from scrapers.base import Job
from tests.support import OfflineTestCase, job

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime.fromisoformat("2026-09-07T12:00:00+00:00")


class MatchingTests(OfflineTestCase):
    def test_regression_benchmark(self):
        data = json.loads((FIXTURES / "matching.json").read_text(encoding="utf-8"))
        config = load_config()
        for row in data["candidates"]:
            with self.subTest(case=row["id"]):
                decision = evaluate_job(Job.from_dict(row["job"]), config, NOW)
                self.assertEqual(decision.tier, row["expected"], decision)

    def test_skill_aliases_do_not_inflate(self):
        self.assertEqual(skills_in("React React.js ReactJS"), {"react"})
        self.assertEqual(skills_in("JavaScript Next.js rapidly Academy"), {"javascript", "nextjs"})
        self.assertEqual(skills_in("C# C++ .NET"), {"csharp", "cpp", "dotnet"})

    def test_experience_ranges_and_context(self):
        requirements = experience_requirements("1 to 3 years experience. A 4 year degree is required.")
        self.assertEqual(len(requirements), 1)
        self.assertEqual(requirements[0].minimum_months, 12)
        self.assertEqual(requirements[0].maximum_months, 36)
        self.assertEqual(experience_requirements("0-2 years experience")[0].minimum_months, 0)
        self.assertTrue(experience_requirements("Five years of experience preferred")[0].preferred)

    def test_profile_and_policy_changes_are_effective(self):
        config = load_config()
        config["profile"]["demonstrated_skills"].remove("nextjs")
        item = job(title="Next.js Developer", description="Next.js required.")
        self.assertEqual(evaluate_job(item, config, NOW).tier, "rejected")
        config = load_config()
        config["matching"]["allow_one_year_stretch"] = False
        self.assertEqual(evaluate_job(job(description="Python. 1 year experience required."), config, NOW).tier, "rejected")

    def test_local_salary_policy_is_independent(self):
        config = load_config()
        config["matching"]["remote_salary_policy"] = "require_usd"
        self.assertEqual(evaluate_job(job(salary_currency="PKR", salary_source="disclosed"), config, NOW).tier, "qualified")
        remote = job(location="Worldwide", is_remote=True, salary_text="PKR 100000 monthly")
        self.assertEqual(evaluate_job(remote, config, NOW).tier, "rejected")

    def test_rank_cannot_override_incompatibility(self):
        config = load_config()
        strong = job("strong", description="Python Django React TypeScript required. Fresh graduates welcome.")
        weak = job("weak", description="", description_status="missing")
        bad = job("bad", location="Lahore, Pakistan")
        for item in (weak, strong, bad):
            evaluate_job(item, config, NOW)
        self.assertEqual(rank_jobs([weak, strong])[0].job_id, strong.job_id)
        self.assertEqual(bad.decision["tier"], "rejected")

    def test_requirement_scope_and_education(self):
        config = load_config()
        for description in (
            "Python. 5 years experience required, 2 years Django experience preferred.",
            "Python. Master's degree required.",
            "React or Vue and Rust required.",
        ):
            with self.subTest(description=description):
                self.assertEqual(evaluate_job(job(description=description), config, NOW).tier, "rejected")
        alternative = job(description="Python Django. Bachelor's degree or 5 years of experience required.")
        self.assertEqual(evaluate_job(alternative, config, NOW).tier, "review")

    def test_remote_infrastructure_is_not_remote_employment(self):
        item = job(description="Python Django. Maintain remote servers.")
        self.assertEqual(item.work_mode, "unknown")
        self.assertEqual(evaluate_job(item, load_config(), NOW).tier, "qualified")

    def test_explicit_foreign_candidate_region_is_rejected(self):
        item = job(location="Worldwide", is_remote=True, candidate_locations="United States, Canada")
        self.assertEqual(evaluate_job(item, load_config(), NOW).tier, "rejected")
