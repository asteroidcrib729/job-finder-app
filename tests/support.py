import unittest
from unittest.mock import patch
from scrapers.base import Job


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        blocker = patch("requests.sessions.Session.request", side_effect=AssertionError("Network is forbidden in offline tests"))
        blocker.start()
        self.addCleanup(blocker.stop)


def job(suffix="one", **changes):
    values = dict(title="Junior Python Developer", company="Fixture", location="Karachi, Pakistan",
                  url="https://example.test/jobs/" + suffix, platform="Fixture",
                  description="Python Django. Fresh graduates welcome.", description_status="full",
                  posted_at="2026-09-06T12:00:00+00:00")
    values.update(changes)
    return Job(**values)
