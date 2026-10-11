"""Tests for install.sh against temp directories."""
import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(REPO, "install.sh")
TOOLS = ("node", "npm", "npx")
FAKE_TOOL = '#!/bin/sh\necho "{tool} {version} $*"\n'


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nvm-shims-test-")
        self.dir = os.path.join(self.tmp, "home", ".local", "bin")

    def run_install(self, *args, path="/usr/bin:/bin"):
        env = {"PATH": path, "HOME": os.path.join(self.tmp, "home")}
        return subprocess.run([INSTALL, *args], env=env, capture_output=True, text=True, timeout=30)

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
        result = self.run_install()
        self.assertIn("NOTE: ", result.stdout)
        self.assertIn("comes before %s/node on PATH" % self.dir, result.stdout)


if __name__ == "__main__":
    unittest.main()
