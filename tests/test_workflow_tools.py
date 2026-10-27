"""Offline checks for extracted workflow logic and the no-inline-code contract."""
import io
import json
import os
import shlex
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from job_finder.automation.failure import main as fail_workflow
from job_finder.diagnostics import discord as discord_diagnostic

ROOT = Path(__file__).resolve().parents[1]


class WorkflowToolsTests(unittest.TestCase):
    def run_diagnostic(self, responses, **overrides):
        environment = {
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/fixture-secret",
            "EXPECTED_SERVER_ID": "456", "MESSAGE_ID": "789", **overrides,
        }
        output = io.StringIO()
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(discord_diagnostic, "get_json", side_effect=responses) as get_json, \
             redirect_stdout(output):
            code = discord_diagnostic.main()
        self.assertNotIn("fixture-secret", output.getvalue())
        return code, output.getvalue(), get_json

    def test_matching_destination_and_receipt_produce_safe_summary(self):
        responses = [(200, {"guild_id": "456", "channel_id": "123", "token": "fixture-secret"}),
                     (200, {"id": "789", "channel_id": "123", "content": "private message"})]
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            code, output, get_json = self.run_diagnostic(responses, GITHUB_STEP_SUMMARY=str(summary))
            self.assertIn('"server_matches": true', summary.read_text())
            self.assertNotIn("fixture-secret", summary.read_text())
        self.assertEqual(code, 0)
        self.assertNotIn("private message", output)
        self.assertEqual(get_json.call_count, 2)
        self.assertTrue(json.loads(output)["message_exists"])

    def test_invalid_inputs_make_no_requests_and_do_not_log_secret(self):
        for overrides in ({"EXPECTED_SERVER_ID": "invalid"}, {"MESSAGE_ID": ""},
                          {"DISCORD_WEBHOOK_URL": "https://example.test/fixture-secret"}):
            with self.subTest(overrides=overrides):
                code, _, request = self.run_diagnostic([], **overrides)
                self.assertEqual(code, 1)
                request.assert_not_called()

    def test_wrong_server_missing_message_and_failed_request_fail(self):
        for responses in (
            [(200, {"guild_id": "999", "channel_id": "123"}), (200, {"id": "789"})],
            [(200, {"guild_id": "456", "channel_id": "123"}), (404, {})],
            [("request_failed", {})],
        ):
            with self.subTest(responses=responses):
                self.assertEqual(self.run_diagnostic(responses)[0], 1)

    def test_transport_is_get_only_rejects_redirects_and_sanitizes_failures(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"guild_id":"456"}'
        with patch("urllib.request.build_opener", return_value=opener) as build:
            self.assertEqual(discord_diagnostic.get_json("https://discord.com/fixture-secret"),
                             (200, {"guild_id": "456"}))
            self.assertIs(build.call_args.args[0], discord_diagnostic.NoRedirect)
            self.assertEqual(opener.open.call_args.args[0].get_method(), "GET")
            response.read.return_value = b'[]'
            self.assertEqual(discord_diagnostic.get_json("https://discord.com/fixture-secret"),
                             ("invalid_response", {}))
            opener.open.side_effect = urllib.error.HTTPError("fixture-secret", 403, "denied", Message(), None)
            self.assertEqual(discord_diagnostic.get_json("https://discord.com/fixture-secret"), (403, {}))
            opener.open.side_effect = OSError("fixture-secret")
            self.assertEqual(discord_diagnostic.get_json("https://discord.com/fixture-secret"),
                             ("request_failed", {}))
        handler = discord_diagnostic.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://example.test"))

    def test_failure_step_returns_nonzero(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(fail_workflow(), 1)

    def test_workflows_only_invoke_tools_or_dedicated_scripts(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job in workflow["jobs"].values():
                for step in job["steps"]:
                    if "run" not in step:
                        continue
                    with self.subTest(workflow=path.name, command=step["run"]):
                        command = step["run"].strip()
                        for embedded in ("\n", "<<", "$(", "`", ";", "&&", "||"):
                            self.assertNotIn(embedded, command)
                        args = shlex.split(command)
                        self.assertEqual(args[0], "uv")
                        self.assertFalse({"-c", "-e", "-Command", "-EncodedCommand"}.intersection(args))
                        self.assertNotEqual(args[-1], "-")
