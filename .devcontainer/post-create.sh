#!/usr/bin/env bash
set -euo pipefail

# postCreateCommand runs with the workspace folder as cwd, so every path here is relative to it:
# hardcoding /workspaces/<repo> breaks whenever the clone directory has a different name.
ROOT="$(pwd)"

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

for app in chat-agent video-search; do
  echo "==> Setting up $app"
  (cd "$ROOT/$app" && uv sync)
done

echo
echo "==> Dev container ready"
echo
echo "    Run the chat agent on Pixeltable Cloud, free for 48 hours, no account:"
echo
echo "      bash .devcontainer/cloud.sh"
echo
echo "    Or run it here:"
echo
echo "    Export your key first (see chat-agent/README.md for why):"
echo
echo "      export ANTHROPIC_API_KEY=sk-...      # only /ask needs this"
echo
echo "    Then:"
echo
echo "      cd chat-agent"
echo "      uv run pxt schema update app.py agent"
echo "      uv run pxt service update app.py agent"
echo "      uv run pxt service list        # the port it picked; VS Code forwards it for you"
echo
echo "    video-search is set up too: cd video-search, TARGET is 'videointel'."
