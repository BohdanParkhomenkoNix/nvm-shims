"""Tests for nvm-shim, run through symlinks against a fake NVM_DIR."""
import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM = os.path.join(REPO, "nvm-shim")
TOOLS = ("node", "npm", "npx")
# A fake tool prints its name, its version dir and its arguments; FAKE_RC sets its exit code.
FAKE_TOOL = '#!/bin/sh\necho "{tool} {version} $*"\nexit "${{FAKE_RC:-0}}"\n'


class ShimTestCase(unittest.TestCase):
    root_prefix = "nvm-shims-test-"

    def setUp(self):
        # realpath: on macOS the temp dir sits behind the /var -> /private/var symlink, and $PWD is the real path.
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix=self.root_prefix))
        self.nvm = os.path.join(self.tmp, "nvm")
        self.shims = os.path.join(self.tmp, "shims")
        self.project = os.path.join(self.tmp, "project")
        os.makedirs(self.shims)
        os.makedirs(self.project)
        for tool in TOOLS:
            os.symlink(SHIM, os.path.join(self.shims, tool))

    def install(self, *versions):
        for version in versions:
            bin_dir = os.path.join(self.nvm, "versions", "node", version, "bin")
            os.makedirs(bin_dir)
            for tool in TOOLS:
                path = os.path.join(bin_dir, tool)
                with open(path, "w") as f:
                    f.write(FAKE_TOOL.format(tool=tool, version=version))
                os.chmod(path, 0o755)

    def alias(self, name, target):
        path = os.path.join(self.nvm, "alias", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(target + "\n")

    def nvmrc(self, content, where=None):
        with open(os.path.join(where or self.project, ".nvmrc"), "w", newline="") as f:
            f.write(content)

    def run_shim(self, tool="node", args=(), cwd=None, env=None):
        full_env = {"PATH": "/usr/bin:/bin", "HOME": self.tmp, "NVM_DIR": self.nvm}
        full_env.update(env or {})
        full_env = {k: v for k, v in full_env.items() if v is not None}  # None unsets a variable
        return subprocess.run(
            [os.path.join(self.shims, tool), *args],
            cwd=cwd or self.project, env=full_env,
            capture_output=True, text=True, timeout=30,
        )

    def assertRuns(self, result, expected):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected)
        self.assertEqual(result.stderr, "")


class NvmrcTest(ShimTestCase):
    def setUp(self):
        super().setUp()
        self.install("v20.20.0", "v22.23.2")
        self.alias("default", "20.20.0")

    def test_exact_version(self):
        self.nvmrc("22.23.2\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_v_prefix_comment_and_whitespace(self):
        self.nvmrc("\n   v22  # project node\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_crlf_nvmrc(self):
        self.nvmrc("22\r\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_found_in_parent_directory(self):
        self.nvmrc("22\n")
        deep = os.path.join(self.project, "a", "b")
        os.makedirs(deep)
        self.assertRuns(self.run_shim(cwd=deep), "node v22.23.2")

    def test_node_means_highest_installed(self):
        self.nvmrc("node\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_beats_nvm_bin(self):
        self.nvmrc("22\n")
        nvm_bin = os.path.join(self.nvm, "versions", "node", "v20.20.0", "bin")
        self.assertRuns(self.run_shim(env={"NVM_BIN": nvm_bin}), "node v22.23.2")

    def test_missing_version(self):
        self.nvmrc("18\n")
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertEqual(
            result.stderr.strip(),
            "nvm-shims: node 18 from %s is not installed: nvm install 18 (NVM_DIR=%s)"
            % (os.path.join(self.project, ".nvmrc"), self.nvm),
        )

    def test_empty_nvmrc(self):
        self.nvmrc("  \n# only a comment\n")
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertIn("nvm-shims: ", result.stderr)
        self.assertIn("is empty", result.stderr)

    def test_dotdot_spec_rejected(self):
        self.nvmrc("../../versions/node/v22.23.2\n")
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertTrue(result.stderr.startswith("nvm-shims: "), result.stderr)

    def test_key_value_lines_are_skipped(self):
        self.nvmrc("foo=bar\n22\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_unreadable_nvmrc_fails_with_message(self):
        if os.geteuid() == 0:
            self.skipTest("root can read any file")
        self.nvmrc("22\n")
        path = os.path.join(self.project, ".nvmrc")
        os.chmod(path, 0o000)
        try:
            result = self.run_shim()
        finally:
            os.chmod(path, 0o644)
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stderr.strip(), "nvm-shims: cannot read %s" % path)


class VersionMatchTest(ShimTestCase):
    def test_major_picks_highest_numerically(self):
        self.install("v20.9.0", "v20.10.0", "v22.1.0")
        self.nvmrc("20\n")
        self.assertRuns(self.run_shim(), "node v20.10.0")

    def test_major_minor_prefix(self):
        self.install("v20.9.3", "v20.10.0")
        self.nvmrc("20.9\n")
        self.assertRuns(self.run_shim(), "node v20.9.3")

    def test_prefix_does_not_match_longer_major(self):
        self.install("v2.0.0", "v20.1.0")
        self.nvmrc("2\n")
        self.assertRuns(self.run_shim(), "node v2.0.0")


class AliasTest(ShimTestCase):
    def setUp(self):
        super().setUp()
        self.install("v20.20.0", "v22.23.2")

    def test_lts_star_chain(self):
        self.alias("lts/iron", "v20.20.0")
        self.alias("lts/*", "lts/iron")
        self.nvmrc("lts/*\n")
        self.assertRuns(self.run_shim(), "node v20.20.0")

    def test_named_alias(self):
        self.alias("work", "22")
        self.nvmrc("work\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_default_alias_chain_without_nvmrc(self):
        self.alias("lts/iron", "20")
        self.alias("default", "lts/iron")
        self.assertRuns(self.run_shim(), "node v20.20.0")

    def test_alias_cycle_fails(self):
        self.alias("a", "b")
        self.alias("b", "a")
        self.nvmrc("a\n")
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertTrue(result.stderr.startswith("nvm-shims: "), result.stderr)

    def test_no_default_alias(self):
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertIn("nvm alias default", result.stderr)
        self.assertIn("NVM_DIR=%s" % self.nvm, result.stderr)

    def test_default_alias_not_installed_names_nvm_dir(self):
        self.alias("default", "18")
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertIn("is not installed: nvm install 18", result.stderr)
        self.assertIn("NVM_DIR=%s" % self.nvm, result.stderr)


class NvmBinTest(ShimTestCase):
    def setUp(self):
        super().setUp()
        self.install("v20.20.0", "v22.23.2")
        self.alias("default", "20")

    def test_used_without_nvmrc(self):
        nvm_bin = os.path.join(self.nvm, "versions", "node", "v22.23.2", "bin")
        self.assertRuns(self.run_shim(env={"NVM_BIN": nvm_bin}), "node v22.23.2")

    def test_nvm_bin_outside_versions_ignored(self):
        self.assertRuns(self.run_shim(env={"NVM_BIN": self.shims}), "node v20.20.0")

    def test_default_without_nvm_bin(self):
        self.assertRuns(self.run_shim(), "node v20.20.0")


class ExecTest(ShimTestCase):
    def setUp(self):
        super().setUp()
        self.install("v20.20.0")
        self.alias("default", "20")

    def test_tool_name_from_symlink(self):
        self.assertRuns(self.run_shim("npx"), "npx v20.20.0")
        self.assertRuns(self.run_shim("npm"), "npm v20.20.0")

    def test_args_pass_through(self):
        self.assertRuns(self.run_shim(args=["-e", "a b", "--x"]), "node v20.20.0 -e a b --x")

    def test_exit_code_passes_through(self):
        self.assertEqual(self.run_shim(env={"FAKE_RC": "3"}).returncode, 3)

    def test_no_args(self):
        self.assertRuns(self.run_shim(), "node v20.20.0")

    def write_env_node_npx(self):
        path = os.path.join(self.nvm, "versions", "node", "v20.20.0", "bin", "npx")
        with open(path, "w") as f:
            f.write("#!/usr/bin/env node\n")

    def test_npx_finds_node_when_shim_dir_is_not_on_path(self):
        self.write_env_node_npx()
        self.assertRuns(self.run_shim("npx"), "node v20.20.0 %s" % os.path.join(
            self.nvm, "versions", "node", "v20.20.0", "bin", "npx"))

    def test_npx_finds_node_through_relative_shim_path(self):
        self.write_env_node_npx()
        result = subprocess.run(
            ["./npx"], cwd=self.shims,
            env={"PATH": "/usr/bin:/bin", "HOME": self.tmp, "NVM_DIR": self.nvm},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("node v20.20.0 "), result.stdout)


class EnvironmentTest(ShimTestCase):
    def test_neither_nvm_dir_nor_home(self):
        for value in (None, ""):
            result = self.run_shim(env={"NVM_DIR": value, "HOME": value})
            self.assertEqual(result.returncode, 127, result.stderr)
            self.assertEqual(result.stderr.strip(), "nvm-shims: neither NVM_DIR nor HOME is set")


class SpacesTest(ShimTestCase):
    root_prefix = "nvm-shims test "

    def test_paths_with_spaces(self):
        self.install("v22.23.2")
        self.nvmrc("22\n")
        self.assertRuns(self.run_shim(args=["x y"]), "node v22.23.2 x y")


class NvmShFallbackTest(ShimTestCase):
    def setUp(self):
        super().setUp()
        self.install("v22.23.2")
        os.makedirs(self.nvm, exist_ok=True)
        with open(os.path.join(self.nvm, "nvm.sh"), "w") as f:
            f.write(
                'nvm() {\n'
                '  [ "$1" = version ] || return 1\n'
                '  case $2 in\n'
                '    weird) echo v22.23.2 ;;\n'
                '    gone) echo v99.0.0 ;;\n'
                '    *) echo N/A ;;\n'
                '  esac\n'
                '}\n'
            )

    def test_uses_nvm_version(self):
        self.nvmrc("weird\n")
        self.assertRuns(self.run_shim(), "node v22.23.2")

    def test_nvm_answer_not_installed(self):
        self.nvmrc("gone\n")
        result = self.run_shim()
        self.assertEqual(result.returncode, 127)
        self.assertTrue(result.stderr.startswith("nvm-shims: "), result.stderr)


if __name__ == "__main__":
    unittest.main()
