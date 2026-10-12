"""The README documents the real install command, the resolution order and the error message."""
import os
import re
import shutil
import subprocess
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


def wrapper_block(lang):
    """The README snippet fenced as `lang` that defines the nvm_ls_current wrapper."""
    for block in re.findall(r"```%s\n(.*?)```" % lang, read("README.md"), re.S):
        if "nvm_ls_current()" in block:
            return block
    raise AssertionError("no %s nvm_ls_current block in README" % lang)


class WrapperSnippetTest(unittest.TestCase):
    def test_zsh_snippet_guards_against_double_wrapping(self):
        self.assertIn(
            "[[ ${functions[nvm_ls_current]} == *_nvm_ls_current_orig* ]] || functions -c nvm_ls_current _nvm_ls_current_orig",
            wrapper_block("zsh"))

    def test_bash_snippet_guards_against_double_wrapping(self):
        self.assertIn(
            "declare -f nvm_ls_current | grep -q _nvm_ls_current_orig || eval",
            wrapper_block("bash"))

    def test_readme_says_snippet_is_safe_to_run_twice(self):
        self.assertIn("safe to run twice", read("README.md"))

    def run_twice(self, argv, lang):
        # A fake stand-in for nvm's function; the real nvm is not needed to prove the wrapping.
        script = "nvm_ls_current() { echo fake-system; }\n%s\n%s\nunset NVM_BIN\nnvm_ls_current\n" % (
            wrapper_block(lang), wrapper_block(lang))
        r = subprocess.run(argv, input=script, capture_output=True, text=True, timeout=20,
                           env={"PATH": "/usr/bin:/bin"})
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (0, "fake-system", ""))

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed")
    def test_zsh_snippet_evaluated_twice_does_not_recurse(self):
        self.run_twice([shutil.which("zsh"), "-f"], "zsh")

    @unittest.skipUnless(os.path.exists("/bin/bash"), "bash not installed")
    def test_bash_snippet_evaluated_twice_does_not_recurse(self):
        self.run_twice(["/bin/bash", "--norc"], "bash")
