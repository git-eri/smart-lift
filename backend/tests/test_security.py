"""Malformed credentials are authentication failures, never server exceptions."""

import os
import unittest
from unittest.mock import patch

from app.core.security import controller_token_valid


class ControllerTokenTests(unittest.TestCase):
    def test_configured_token_rejects_unicode_and_unencodable_input(self):
        with patch.dict(os.environ, {"SMARTLIFT_CONTROLLER_TOKEN": "expected-ascii-token"}):
            self.assertTrue(controller_token_valid("expected-ascii-token"))
            for value in [None, "", "wrong", "caf\u00e9", "\ud800"]:
                with self.subTest(value=repr(value)):
                    self.assertFalse(controller_token_valid(value))

    def test_unset_token_keeps_trusted_lan_mode(self):
        with patch.dict(os.environ, {"SMARTLIFT_CONTROLLER_TOKEN": ""}):
            self.assertTrue(controller_token_valid(None))
