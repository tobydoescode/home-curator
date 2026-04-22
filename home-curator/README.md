# Home Curator Addon

Install by adding this repo to Home Assistant:

**Settings → Add-ons → Add-on Store → ⋮ → Repositories → paste URL**.

Then install "Home Curator" and open it from the sidebar. On first start a default `policies.yaml` is created at `/config/home-curator/policies.yaml`. Edit it directly (the UI also edits a subset of the file via Settings → Naming Conventions) to configure:

- naming-convention rules (global + per-room overrides)
- missing-area detection
- reappeared-after-delete detection
- custom CEL expressions

## Logs

See the addon's logs for rule-engine errors and HA websocket reconnects.
