"""Unit tests for botcore_checks.py — no botcore install required.

Run with: python -m unittest discover <this directory>
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import botcore_checks


def _ok(data=None):
    async def fn(path=None):
        return SimpleNamespace(success=True, error=None, data=data)

    return fn


def _fail(error):
    async def fn(path=None):
        return SimpleNamespace(success=False, error=error, data=None)

    return fn


def _old_botcore():
    async def fn():  # no `path` kwarg, like pre-2e7df33 botcore
        raise AssertionError("should not be reached")

    return fn


class RunScopedTests(unittest.TestCase):
    def test_no_source_dirs_is_an_error_not_a_pass(self):
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            code = botcore_checks.run_scoped(_ok(), cwd=Path(tmp))
        self.assertEqual(code, 2)
        self.assertIn("none of", out.getvalue())

    def test_passes_when_all_dirs_clean(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "packages").mkdir()
            code = botcore_checks.run_scoped(_ok(), cwd=Path(tmp))
        self.assertEqual(code, 0)

    def test_failed_result_prints_message_and_fails(self):
        err = SimpleNamespace(message="Files exceeding 2300 lines: big.ts (9000)")
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            (Path(tmp) / "packages").mkdir()
            code = botcore_checks.run_scoped(_fail(err), cwd=Path(tmp))
        self.assertEqual(code, 1)
        self.assertIn("Files exceeding 2300 lines", out.getvalue())

    def test_failed_result_without_error_object_does_not_raise(self):
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            (Path(tmp) / "packages").mkdir()
            code = botcore_checks.run_scoped(_fail(None), cwd=Path(tmp))
        self.assertEqual(code, 1)
        self.assertIn("failed without error detail", out.getvalue())

    def test_old_botcore_without_path_kwarg_is_an_error(self):
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            (Path(tmp) / "packages").mkdir()
            code = botcore_checks.run_scoped(_old_botcore(), cwd=Path(tmp))
        self.assertEqual(code, 2)
        self.assertIn("botcore too old", out.getvalue())


class RunGlobalTests(unittest.TestCase):
    def test_passes_on_success_without_drift(self):
        self.assertEqual(botcore_checks.run_global(_ok(data={"drift": False})), 0)

    def test_prints_message_and_fails(self):
        err = SimpleNamespace(message="Circular dependency: a -> b -> a")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = botcore_checks.run_global(_fail(err))
        self.assertEqual(code, 1)
        self.assertIn("Circular dependency", out.getvalue())

    def test_lockfile_drift_warning_fails_the_gate(self):
        # dev_check_lockfile is warning-only upstream: success=True with drift data
        data = {
            "drift": True,
            "warnings": [{"message": "pnpm-lock.yaml changed without a manifest file change"}],
        }
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = botcore_checks.run_global(_ok(data=data))
        self.assertEqual(code, 1)
        self.assertIn("pnpm-lock.yaml changed", out.getvalue())


class MainTests(unittest.TestCase):
    def test_dispatch_routes_scoped_and_global(self):
        import types

        fake_dev = types.ModuleType("botcore.commands.dev")
        fake_dev.dev_check_size = "SIZE_FN"
        fake_dev.dev_check_paths = "PATHS_FN"
        fake_dev.dev_circular_imports = "CIRC_FN"
        fake_quality = types.ModuleType("botcore.commands.dev.quality")
        fake_quality.dev_check_lockfile = "LOCK_FN"
        modules = {
            "botcore": types.ModuleType("botcore"),
            "botcore.commands": types.ModuleType("botcore.commands"),
            "botcore.commands.dev": fake_dev,
            "botcore.commands.dev.quality": fake_quality,
        }
        with (
            patch.dict(sys.modules, modules),
            patch.object(botcore_checks, "run_scoped", return_value=0) as scoped,
            patch.object(botcore_checks, "run_global", return_value=0) as global_,
        ):
            self.assertEqual(botcore_checks.main("check-size"), 0)
            scoped.assert_called_once_with("SIZE_FN")
            self.assertEqual(botcore_checks.main("lockfile-drift"), 0)
            global_.assert_called_once_with("LOCK_FN")

    def test_unknown_check_exits_2(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(botcore_checks.main("bogus"), 2)
        self.assertIn("unknown check", out.getvalue())

    def test_missing_botcore_exits_2_with_hint(self):
        # A None entry in sys.modules makes `import botcore...` raise ImportError
        with (
            patch.dict(sys.modules, {"botcore": None}),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(botcore_checks.main("check-size"), 2)
        self.assertIn("botcore not importable", out.getvalue())


class FailMessageTests(unittest.TestCase):
    def test_prefers_error_message(self):
        r = SimpleNamespace(success=False, error=SimpleNamespace(message="boom"))
        self.assertEqual(botcore_checks.fail_message(r), "boom")

    def test_falls_back_to_str_of_error(self):
        r = SimpleNamespace(success=False, error="raw error")
        self.assertEqual(botcore_checks.fail_message(r), "raw error")

    def test_handles_missing_error(self):
        r = SimpleNamespace(success=False, error=None)
        self.assertEqual(botcore_checks.fail_message(r), "failed without error detail")


if __name__ == "__main__":
    unittest.main()
