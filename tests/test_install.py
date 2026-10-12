"""Tests for install.sh against temp directories."""
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(REPO, "install.sh")
TOOLS = ("node", "npm", "npx")
FAKE_TOOL = '#!/bin/sh\necho "{tool} {version} $*"\n'


class InstallTest(unittest.TestCase):
    def setUp(self):
        # realpath: install.sh prints physical paths, and the temp dir sits behind /var -> /private/var on macOS.
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="nvm-shims-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dir = os.path.join(self.tmp, "home", ".local", "bin")

    def run_install(self, *args, path="/usr/bin:/bin", cwd=None):
        env = {"PATH": path, "HOME": os.path.join(self.tmp, "home")}
        return subprocess.run([INSTALL, *args], env=env, cwd=cwd, capture_output=True, text=True, timeout=30)

    def assertLinked(self):
        for tool in TOOLS:
            link = os.path.join(self.dir, tool)
            self.assertTrue(os.path.islink(link), link)
            self.assertEqual(os.readlink(link), os.path.join(REPO, "bin", tool))

    def test_default_dir_is_created_and_linked(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLinked()
        self.assertIn("linked %s/node -> %s/bin/node" % (self.dir, REPO), result.stdout)

    def test_explicit_dir(self):
        self.dir = os.path.join(self.tmp, "other bin")
        result = self.run_install(self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLinked()

    def test_installed_link_runs_the_shim(self):
        self.assertEqual(self.run_install().returncode, 0)
        nvm = os.path.join(self.tmp, "nvm")
        bin_dir = os.path.join(nvm, "versions", "node", "v20.20.0", "bin")
        os.makedirs(bin_dir)
        with open(os.path.join(bin_dir, "node"), "w") as f:
            f.write(FAKE_TOOL.format(tool="node", version="v20.20.0"))
        os.chmod(os.path.join(bin_dir, "node"), 0o755)
        os.makedirs(os.path.join(nvm, "alias"))
        with open(os.path.join(nvm, "alias", "default"), "w") as f:
            f.write("20\n")
        result = subprocess.run(
            [os.path.join(self.dir, "node"), "-v"], cwd=self.tmp,
            env={"PATH": "/usr/bin:/bin", "HOME": self.tmp, "NVM_DIR": nvm},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.stdout.strip(), "node v20.20.0 -v", result.stderr)

    def test_existing_symlink_is_replaced(self):
        os.makedirs(self.dir)
        os.symlink("/nonexistent/node", os.path.join(self.dir, "node"))
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLinked()

    def test_regular_file_stops_install(self):
        os.makedirs(self.dir)
        npm = os.path.join(self.dir, "npm")
        with open(npm, "w") as f:
            f.write("keep me\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 1)
        self.assertIn("nvm-shims: ", result.stderr)
        self.assertIn(npm, result.stderr)
        with open(npm) as f:
            self.assertEqual(f.read(), "keep me\n")
        self.assertFalse(os.path.lexists(os.path.join(self.dir, "node")))

    def test_idempotent(self):
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(self.run_install().returncode, 0)
        self.assertLinked()

    def test_reports_path_order_ok(self):
        result = self.run_install(path=self.dir + ":/usr/bin:/bin")
        self.assertIn("OK: %s/node is the first node on PATH" % self.dir, result.stdout)

    def test_reports_path_order_note(self):
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        with open(os.path.join(other, "node"), "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(os.path.join(other, "node"), 0o755)
        result = self.run_install(path="%s:%s:/usr/bin:/bin" % (other, self.dir))
        self.assertIn("NOTE: %s/node comes before %s/node on PATH" % (other, self.dir), result.stdout)

    def test_reports_dir_not_on_path(self):
        result = self.run_install()
        self.assertIn("NOTE: %s is not on PATH; add it to PATH, after nvm is loaded" % self.dir, result.stdout)
        self.assertNotIn("comes before", result.stdout)

    def test_trailing_slash_dir_is_normalised(self):
        result = self.run_install(self.dir + "/", path=self.dir + ":/usr/bin:/bin")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLinked()
        self.assertIn("linked %s/node -> %s/bin/node" % (self.dir, REPO), result.stdout)
        self.assertIn("OK: %s/node is the first node on PATH" % self.dir, result.stdout)
        self.assertNotIn("NOTE", result.stdout)

    def test_relative_dir_is_made_absolute(self):
        result = self.run_install(os.path.join("home", ".local", "bin"), path=self.dir + ":/usr/bin:/bin",
                                  cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLinked()
        self.assertIn("linked %s/node -> %s/bin/node" % (self.dir, REPO), result.stdout)
        self.assertIn("OK: %s/node is the first node on PATH" % self.dir, result.stdout)
        self.assertNotIn("NOTE", result.stdout)

    def test_directory_in_place_of_a_tool_stops_install(self):
        os.makedirs(os.path.join(self.dir, "npx"))
        keep = os.path.join(self.dir, "npx", "keep")
        with open(keep, "w") as f:
            f.write("keep me\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("nvm-shims: "), result.stderr)
        self.assertIn(os.path.join(self.dir, "npx"), result.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.dir, "npx")))
        self.assertFalse(os.path.islink(os.path.join(self.dir, "npx")))
        self.assertEqual(os.listdir(os.path.join(self.dir, "npx")), ["keep"])
        self.assertEqual(sorted(os.listdir(self.dir)), ["npx"])

    def test_dir_matches_whole_path_entries_only(self):
        result = self.run_install(path=self.dir + "-x:/usr/bin:/bin")
        self.assertIn("is not on PATH", result.stdout)

    def test_no_argument_and_no_home_fails(self):
        result = subprocess.run([INSTALL], env={"PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("nvm-shims: "), result.stderr)

    def test_repo_bin_is_refused_as_dir(self):
        # A copy of the repository, so the real bin/ is never touched.
        copy = os.path.join(self.tmp, "copy")
        os.makedirs(os.path.join(copy, "bin"))
        for name in ("install.sh", "nvm-shim"):
            shutil.copy2(os.path.join(REPO, name), os.path.join(copy, name))
        for tool in TOOLS:
            os.symlink("../nvm-shim", os.path.join(copy, "bin", tool))
        result = subprocess.run(
            [os.path.join(copy, "install.sh"), os.path.join(copy, "bin")],
            env={"PATH": "/usr/bin:/bin", "HOME": self.tmp}, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("nvm-shims: "), result.stderr)
        for tool in TOOLS:
            self.assertEqual(os.readlink(os.path.join(copy, "bin", tool)), "../nvm-shim")


if __name__ == "__main__":
    unittest.main()
