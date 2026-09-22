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
| thumbnail-circle | 0.1.0 | Floating circular window showing the current track's artwork |
| nowplaying | 0.1.0 | Polls and prints the current track via the flow plugin API |

## Adding a plugin

1. Add a `plugins/<name>/` directory with a `main.py` entry point.
2. Add a catalog entry in `manifest.json`.
3. Use the bundled `flow_api` module to interact with Flow (it is injected at install time).
