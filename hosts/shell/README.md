# Goalkeeper — shell host

Use Goalkeeper from a bare shell or CI, with no plugin and no install.

```bash
# run directly
python3 bin/goalkeeper --version

# or put it on PATH
./hosts/shell/install.sh ~/.local/bin
goalkeeper init --template code-refactor -o "…"
```

The entrypoint locates `goalkeeper_core` by walking up from its own (realpath-resolved)
location, or via `GOALKEEPER_CORE_HOME`. Everything is Python 3 stdlib — no `pip install`.
