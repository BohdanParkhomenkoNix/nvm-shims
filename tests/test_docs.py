"""The README documents the real install command, the resolution order and the error message."""
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name):
    with open(os.path.join(REPO, name)) as f:
        return f.read()


class DocsTest(unittest.TestCase):
    def test_readme_covers_install_order_and_message(self):
        readme = read("README.md")
        for needle in (
            "./install.sh",
            "`.nvmrc`",
            "`$NVM_BIN`",
            "nvm alias default",
            "is not installed: nvm install",
            "`NVM_DIR` defaults to `~/.nvm`",
            "fnm switches versions per shell",
            "load-nvmrc",
            "NVM_BIN:h:t",
            "nvshim",
            "nevermind",
            "_nvm_ls_current_orig",
        ):
            self.assertIn(needle, readme)

    def test_license_is_mit(self):
        licence = read("LICENSE")
        self.assertIn("MIT License", licence)
        self.assertIn("Copyright (c) 2026 Bohdan Parkhomenko", licence)

    def test_ci_runs_tests_and_shellcheck_on_both_oses(self):
        ci = read(".github/workflows/ci.yml")
        for needle in ("ubuntu-latest", "macos-latest", "shellcheck nvm-shim install.sh",
                       "python3 -m unittest discover -s tests -v"):
            self.assertIn(needle, ci)

    def test_ci_checkout_runs_on_node24(self):
        # actions/checkout@v4 runs on the deprecated Node 20; v7 is the newest major, with `using: node24`.
        self.assertIn("actions/checkout@v7", read(".github/workflows/ci.yml"))
