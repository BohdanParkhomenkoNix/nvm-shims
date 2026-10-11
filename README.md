# nvm-shims

`node`, `npm` and `npx` that work where nvm does not: GUI apps, launchd/systemd services, MCP servers
started by AI tools, and agent shells that never run your `.zshrc` hooks.

nvm puts `~/.nvm/versions/node/<version>/bin` on `PATH` from your shell rc file. Anything not started
from that shell gets no node at all. MCP clients then fail with `spawn npx ENOENT`. The common fixes pin
one version (`/Users/you/.nvm/versions/node/v22.14.0/bin/npx`) and break on the next `nvm install`.

nvm-shims is one bash script. Run as `node`, `npm` or `npx`, it picks the version and `exec`s the real
binary:

1. `.nvmrc` in the current directory or any parent;
2. otherwise `$NVM_BIN`, the version the calling shell is using (so `nvm use 22` keeps working);
3. otherwise the version named by `nvm alias default`.

It understands `22`, `v22.23.2`, `22.23`, `node`, `stable`, `lts/*`, `lts/<name>` and your own
aliases by reading nvm's alias files. For anything else it asks `nvm version` in a subshell. It never
installs anything. A missing version is an error:

```
nvm-shims: node 18 from /path/to/project/.nvmrc is not installed: nvm install 18
```

## Install

```sh
git clone https://github.com/BohdanParkhomenkoNix/nvm-shims.git ~/Projects/nvm-shims
cd ~/Projects/nvm-shims
./install.sh            # links ~/.local/bin/{node,npm,npx}
./install.sh /some/bin  # or another directory
```

`install.sh` refuses to overwrite a regular file, and replaces an existing symlink. At the end it says
whether the shims are first on your `PATH`.

**PATH order matters.** Services and GUI apps need the directory on their own `PATH`. `~/.local/bin`
is a common choice, and for a launchd agent or a systemd unit you set `PATH` there. In your shell, put
the directory **after** nvm is loaded, so it comes before nvm's `bin`:

```sh
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
export PATH="$HOME/.local/bin:$PATH"
```

To uninstall, delete the three symlinks `install.sh` printed.

## The `load-nvmrc` hook

nvm decides the "current" version from the `node` it finds on `PATH`. With a shim first, `nvm current`
says `system`. The popular zsh hook `load-nvmrc` compares against `nvm version`, so it would run
`nvm use` on every `cd`. Compare against `$NVM_BIN` instead:

```zsh
load-nvmrc() {
  local nvmrc_path="$(nvm_find_nvmrc)"
  local current_version=none
  [ -n "$NVM_BIN" ] && current_version="${NVM_BIN:h:t}"
  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")
    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$current_version" ]; then
      nvm use
    fi
  elif [ -n "$(PWD=$OLDPWD nvm_find_nvmrc)" ] && [ "$current_version" != "$(nvm version default)" ]; then
    nvm use default
  fi
}
```

## Limitations

- Only `node`, `npm` and `npx` are shimmed. Global packages (`pnpm`, `tsc`, …) live in a version's own
  `bin`, but their `#!/usr/bin/env node` line still goes through the shim.
- `nvm current` and `nvm ls` show `system` while a shim is first on `PATH`.
- macOS and Linux, bash 3.2 or newer. No Windows.

## Alternatives

- [iamogbz/nvshim](https://github.com/iamogbz/nvshim): Python (`pip install nvshim`). Also shims
  `nvm`, and wants you to stop sourcing `nvm.sh` in your shell. Every call goes through `nvm exec`.
- [bozdoz/nevermind](https://pkg.go.dev/github.com/bozdoz/nevermind/nvm-shim): a Go binary that also
  shims globally installed npm binaries.
- volta, fnm and mise have shims built in, if you are willing to replace nvm.

nvm-shims keeps nvm exactly as it is and adds one dependency-free script.

## Development

```sh
python3 -m unittest discover -s tests -v
shellcheck nvm-shim install.sh
```

MIT licensed.
