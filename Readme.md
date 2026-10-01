# flow-plugins

Community plugin repository for the [Flow music player](https://github.com/Twinx015/Flow).

## Install a plugin

```bash
flow install <plugin-name>          # from the default repo
flow install Twinx015/harpy         # from a different user's repo
```

## List available plugins

```bash
flow plugins list
```

## Run a plugin

```bash
flow run <plugin-name>
```

## Uninstall

```bash
flow uninstall <plugin-name>
```

## Plugins

| Name | Version | Description |
|------|---------|-------------|
| auto-stop | 0.1.0 | Pauses Flow when another MPRIS player (Zen, Firefox, …) starts playing |

### auto-stop

Stops the music when someone else takes over: watches `playerctl -l` and pauses
Flow whenever Zen, a browser, or any other MPRIS player reports `Playing`.

```bash
flow install auto-stop
flow run auto-stop                       # backgrounds it
flow run auto-stop --ignore spotify -v   # args pass through
flow plugin kill auto-stop
```

Needs `playerctl` on `PATH`. Background runs log to
`~/.flow/plugins/_logs/auto-stop.log`. Full docs, including how to tune
the poll interval and why it reads Flow's state over MPRIS, are in
[`plugins/auto-stop/README.md`](plugins/auto-stop/README.md).

## Adding a plugin

1. Add a `plugins/<name>/` directory with a `main.py` entry point.
2. Add a catalog entry in `manifest.json` (the directory name must match the
   entry's `name`, and `api_version` must be `3`).
3. Use the bundled `flow_api` module to interact with Flow (injected at install
   time).
4. `bg` decides how `flow run` launches the plugin: `true` backgrounds it
   (default, stop with `flow plugin kill <name>`), `false` runs it in the
   foreground (Ctrl-C stops it) — use `"bg": false` for console plugins like
   `nowplaying` that need the terminal.

## See docs at the official repo for ref.
