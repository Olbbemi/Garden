"""Exercise Garden's project hook and linker in isolated local Git repositories."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LINKER = ROOT / "scripts/link_codex_agents.py"
TODO_LINKER = ROOT / "scripts/link_shared_todo.py"
PROJECT_HOOK = ROOT / "tools/scripts/git/post-checkout"
GARDEN = "https://github.com/Olbbemi/Garden.git"


class GardenSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.access(PROJECT_HOOK, os.X_OK):
            raise RuntimeError("Garden project hook must be executable: " + str(PROJECT_HOOK))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="garden setup test ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        # Only child processes see this environment; the user's HOME is untouched.
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_")
            and key not in {"HOME", "XDG_CONFIG_HOME", "CODEX_HOME", "PYTHONPATH", "PYTHONHOME"}
        }
        self.env.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(self.home / ".gitconfig"),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ALLOW_PROTOCOL": "file",
        })
        self.template = self.base / "test hook template"
        self.template.mkdir()
        self.link = self.home / ".codex/AGENTS.md"
        self.storage = self.home / ".local/share/garden"
        self.todo = self.storage / "todo"
        self.source = self.base / "source"
        self.git("init", "--template=", "-b", "main", str(self.source))
        (self.source / "AGENTS.md").write_text("Garden project-only instructions\n")
        (self.source / "global").mkdir()
        (self.source / "global/AGENTS.md").write_text("Shared test instructions\n")
        (self.source / "scripts").mkdir()
        shutil.copy2(LINKER, self.source / "scripts/link_codex_agents.py")
        shutil.copy2(TODO_LINKER, self.source / "scripts/link_shared_todo.py")
        (self.source / "data/todo").mkdir(parents=True)
        (self.source / "data/todo/README.md").write_text("Garden todo\n")
        (self.source / "tools/scripts/git").mkdir(parents=True)
        shutil.copy2(PROJECT_HOOK, self.source / "tools/scripts/git/post-checkout")
        self.git("add", ".", cwd=self.source)
        self.git("-c", "user.name=Garden Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgSign=false", "commit", "-m", "Test fixture", cwd=self.source)
        self.map_url(GARDEN)

    def run_command(self, *args, cwd=None, ok=True):
        result = subprocess.run(args, cwd=cwd or self.base, env=self.env,
                                text=True, capture_output=True, timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def git(self, *args, **kwargs):
        return self.run_command("git", *args, **kwargs)

    def enable_project_hook(self):
        # Test-only adapter: Git supplies real event arguments and the worktree cwd.
        # Common hook installation and dispatch are tested by their owning project.
        hook = self.template / "hooks/post-checkout"
        hook.parent.mkdir()
        hook.write_text('#!/bin/sh\nexec ./tools/scripts/git/post-checkout "$@"\n')
        hook.chmod(0o755)

    def link_instructions(self, *args, **kwargs):
        return self.run_command(sys.executable, str(LINKER), *args, **kwargs)

    def link_todo(self, *args, **kwargs):
        return self.run_command(sys.executable, "-B", str(TODO_LINKER), *args, **kwargs)

    def map_url(self, url):
        self.git("config", "--global", "--add",
                 f"url.{self.source.as_uri()}.insteadOf", url)

    def clone(self, url=GARDEN, name="cloned Garden", flags=(), ok=True):
        dest = self.base / name
        result = self.git("clone", "--template=" + str(self.template), *flags, url, str(dest), ok=ok)
        return dest, result

    def test_initial_clone_and_live_original(self):
        self.enable_project_hook()
        self.assertFalse(self.link.parent.exists())
        clone, _ = self.clone()
        self.assertTrue(self.link.is_symlink())
        self.assertEqual(self.link.resolve(), clone / "global/AGENTS.md")
        self.assertTrue(self.storage.is_symlink())
        self.assertFalse(self.todo.is_symlink())
        self.assertEqual(self.storage.resolve(), clone / "data")
        self.assertEqual(self.todo.resolve(), clone / "data/todo")
        (self.todo / "task.md").write_text("Pending task\n")
        self.assertEqual((clone / "data/todo/task.md").read_text(), "Pending task\n")
        (clone / "data/assets").mkdir()
        (self.storage / "assets/keep.txt").write_text("Other project data\n")
        self.link_todo(str(clone))
        self.assertEqual((clone / "data/assets/keep.txt").read_text(), "Other project data\n")
        self.assertTrue(os.access(clone / "tools/scripts/git/post-checkout", os.X_OK))
        self.assertEqual(self.link.read_text(), "Shared test instructions\n")
        (clone / "AGENTS.md").write_text("Changed project-only instructions\n")
        self.assertEqual(self.link.read_text(), "Shared test instructions\n")
        (clone / "global/AGENTS.md").write_text("Changed original\n")
        self.assertEqual(self.link.read_text(), "Changed original\n")
        self.link_instructions(str(clone))

    def test_custom_codex_home_and_ssh_origins(self):
        self.env["CODEX_HOME"] = str(self.base / "codex profile")
        destination = Path(self.env["CODEX_HOME"]) / "AGENTS.md"
        self.enable_project_hook()
        urls = ("git@github.com:Olbbemi/Garden.git", "ssh://git@github.com/Olbbemi/Garden")
        for index, url in enumerate(urls):
            with self.subTest(url=url):
                self.map_url(url)
                clone, _ = self.clone(url, name=f"ssh clone {index}")
                self.assertEqual(destination.resolve(), clone / "global/AGENTS.md")
                self.assertFalse(self.link.exists())
                self.assertEqual(self.todo.resolve(), clone / "data/todo")
                destination.unlink()
                self.storage.unlink()

    def test_other_repository_named_garden_is_ignored(self):
        url = "https://github.com/AnotherOwner/Garden.git"
        self.map_url(url)
        self.enable_project_hook()
        self.clone(url, name="Garden")
        self.assertFalse(self.link.parent.exists())
        self.assertFalse(self.todo.parent.exists())

    def test_checkout_switch_and_worktree_do_not_recreate_link(self):
        self.enable_project_hook()
        clone, _ = self.clone()
        self.link.unlink()
        self.storage.unlink()
        self.git("checkout", "--", "AGENTS.md", cwd=clone)
        self.git("switch", "-c", "another", cwd=clone)
        self.git("worktree", "add", "--detach", str(self.base / "worktree"), cwd=clone)
        self.assertFalse(self.link.exists())
        self.assertFalse(self.todo.exists())

    def test_no_checkout_requires_manual_link(self):
        self.enable_project_hook()
        clone, _ = self.clone(flags=("--no-checkout",))
        self.assertFalse(self.link.exists())
        self.assertFalse(self.todo.exists())
        self.git("reset", "--hard", "HEAD", cwd=clone)
        self.link_instructions(str(clone))
        self.assertEqual(self.link.resolve(), clone / "global/AGENTS.md")
        self.link_todo(str(clone))
        self.assertEqual(self.todo.resolve(), clone / "data/todo")

    def test_instruction_destination_conflicts_are_preserved(self):
        self.link.parent.mkdir()
        self.enable_project_hook()
        for kind in ("file", "directory", "broken-link"):
            with self.subTest(kind=kind):
                if kind == "file":
                    self.link.write_text("Existing instructions\n")
                elif kind == "directory":
                    self.link.mkdir()
                    (self.link / "keep").write_text("Existing directory\n")
                else:
                    self.link.symlink_to(self.base / "missing")
                _, result = self.clone(name=kind, ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)
                self.assertFalse(self.storage.exists())
                if kind == "directory":
                    self.assertEqual((self.link / "keep").read_text(), "Existing directory\n")
                    shutil.rmtree(self.link)
                else:
                    if kind == "file":
                        self.assertEqual(self.link.read_text(), "Existing instructions\n")
                    else:
                        self.assertEqual(self.link.readlink(), self.base / "missing")
                    self.link.unlink()

    def test_missing_or_external_instructions_are_rejected(self):
        clone, _ = self.clone()
        external = self.base / "external instructions"
        external.write_text("Outside checkout\n")
        source = clone / "global/AGENTS.md"
        source.unlink()
        for kind in ("missing", "external"):
            with self.subTest(kind=kind):
                if kind == "external":
                    source.symlink_to(external)
                result = self.link_instructions(str(clone), ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("instructions are missing or outside", result.stderr)
                self.assertFalse(self.link.parent.exists())
                self.assertTrue((clone / "AGENTS.md").is_file())

    def test_manual_setup_and_preview_preserve_git_config(self):
        clone, _ = self.clone()
        config = (self.home / ".gitconfig").read_bytes()
        source = clone / "data"
        for data_present in (True, False):
            with self.subTest(data_present=data_present):
                if not data_present:
                    shutil.rmtree(source)
                preview = self.link_todo(str(clone), "--dry-run")
                self.assertIn("Would link:", preview.stdout)
                if not data_present:
                    self.assertIn("Would create directory:", preview.stdout)
                self.assertEqual(source.exists(), data_present)
                self.assertFalse(self.storage.exists())
                self.link_instructions(str(clone))
                self.link_todo(str(clone))
                self.assertEqual(self.link.resolve(), clone / "global/AGENTS.md")
                self.assertTrue(self.todo.is_dir())
                self.assertEqual(self.todo.resolve(), source / "todo")
                self.assertEqual((self.home / ".gitconfig").read_bytes(), config)
                self.assertFalse((clone / ".git/hooks/post-checkout").exists())
                self.link.unlink()
                self.storage.unlink()

    def test_storage_conflicts_are_preserved_before_instructions_are_linked(self):
        self.enable_project_hook()
        self.storage.parent.mkdir(parents=True)
        target = self.base / "other todo"
        target.mkdir()
        for kind in ("file", "directory", "other-link", "broken-link"):
            with self.subTest(kind=kind):
                if kind == "file":
                    self.storage.write_text("Keep file\n")
                elif kind == "directory":
                    self.storage.mkdir()
                    (self.storage / "keep.md").write_text("Keep directory\n")
                else:
                    self.storage.symlink_to(target if kind == "other-link" else self.base / "missing")
                _, result = self.clone(name=kind, ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)
                self.assertFalse(self.link.exists())
                if kind == "directory":
                    self.assertEqual((self.storage / "keep.md").read_text(), "Keep directory\n")
                    shutil.rmtree(self.storage)
                else:
                    if kind == "file":
                        self.assertEqual(self.storage.read_text(), "Keep file\n")
                    else:
                        self.assertEqual(self.storage.readlink(), target if kind == "other-link" else self.base / "missing")
                    self.storage.unlink()

    def test_storage_parent_conflicts_are_preserved(self):
        self.enable_project_hook()
        self.storage.parent.parent.mkdir(parents=True)
        for kind in ("file", "broken-link"):
            with self.subTest(kind=kind):
                if kind == "file":
                    self.storage.parent.write_text("Keep parent\n")
                else:
                    self.storage.parent.symlink_to(self.base / "missing")
                _, result = self.clone(name=kind, ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Parent is not a directory", result.stderr)
                self.assertFalse(self.link.exists())
                if kind == "file":
                    self.assertEqual(self.storage.parent.read_text(), "Keep parent\n")
                else:
                    self.assertEqual(self.storage.parent.readlink(), self.base / "missing")
                self.storage.parent.unlink()

    def test_initial_clone_creates_missing_data_and_todo(self):
        self.git("rm", "-r", "data", cwd=self.source)
        self.git("-c", "user.name=Garden Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgSign=false", "commit", "-m", "Remove data fixture",
                 cwd=self.source)
        self.enable_project_hook()
        clone, _ = self.clone()
        self.assertTrue((clone / "data/todo").is_dir())
        self.assertEqual(list((clone / "data/todo").iterdir()), [])
        self.assertEqual(self.todo.resolve(), clone / "data/todo")
        self.assertEqual(self.link.resolve(), clone / "global/AGENTS.md")

    def test_missing_storage_directories_are_recreated(self):
        self.enable_project_hook()
        clone, _ = self.clone()
        target = self.storage.readlink()
        for relative in ("data/todo", "data"):
            with self.subTest(relative=relative):
                source = clone / relative
                shutil.rmtree(source)
                self.link_todo(str(clone), "--dry-run")
                self.assertFalse(source.exists())
                self.link_todo(str(clone))
                self.assertEqual(self.storage.readlink(), target)
                self.assertEqual(self.todo.resolve(), clone / "data/todo")
                self.assertTrue(self.todo.is_dir())
                self.assertFalse(self.todo.is_symlink())

    def test_source_storage_conflicts_are_preserved(self):
        clone, _ = self.clone()
        external = self.base / "external data"
        external.mkdir()
        for relative in ("data/todo", "data"):
            source = clone / relative
            shutil.rmtree(source)
            for kind in ("file", "external-link", "broken-link"):
                with self.subTest(relative=relative, kind=kind):
                    target = external if kind == "external-link" else clone / "missing"
                    if kind == "file":
                        source.write_text("Keep data file\n")
                    else:
                        source.symlink_to(target)
                    result = self.link_todo(str(clone), ok=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("not a directory or are outside", result.stderr)
                    self.assertFalse(self.storage.exists())
                    self.assertFalse((external / "todo").exists())
                    if kind == "file":
                        self.assertEqual(source.read_text(), "Keep data file\n")
                    else:
                        self.assertEqual(source.readlink(), target)
                    source.unlink()

    def test_storage_conflict_does_not_create_missing_data(self):
        clone, _ = self.clone()
        source = clone / "data"
        shutil.rmtree(source)
        self.storage.parent.mkdir(parents=True)
        self.storage.write_text("Keep todo file\n")
        result = self.link_todo(str(clone), ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertFalse(source.exists())
        self.assertEqual(self.storage.read_text(), "Keep todo file\n")

    def test_manual_linkers_reject_other_repository(self):
        for linker in (self.link_instructions, self.link_todo):
            with self.subTest(linker=linker.__name__):
                result = linker(str(self.source), ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("origin is not", result.stderr)
                self.assertFalse(self.link.parent.exists())
                self.assertFalse(self.storage.exists())

    def test_relative_codex_home_is_rejected(self):
        self.env["CODEX_HOME"] = "relative profile"
        clone, _ = self.clone()
        result = self.link_instructions(str(clone), ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute path", result.stderr)
        self.assertFalse((self.base / "relative profile").exists())


if __name__ == "__main__":
    unittest.main()
