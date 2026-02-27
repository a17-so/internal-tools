# Runbook

## Install

```bash
cd /Users/rootb/Code/a17/internal-tools/outreach-tool-automation
chmod +x ops/install_daemons.sh ops/uninstall_daemons.sh
./ops/install_daemons.sh
```

## Verify

```bash
sudo launchctl list | rg outreach
```

If using ADC (no service account key), authenticate once:

```bash
gcloud auth application-default login
```

Run one manual dry-run:

```bash
cd /Users/rootb/Code/a17/internal-tools/outreach-tool-automation
source .venv/bin/activate
python -m outreach_automation.run_once --dry-run --max-leads 5
```

## Logs

- `logs/daemon.out.log`
- `logs/daemon.err.log`
- `logs/reset.out.log`
- `logs/reset.err.log`

## Stop / Remove

```bash
cd /Users/rootb/Code/a17/internal-tools/outreach-tool-automation
./ops/uninstall_daemons.sh
```

## Recovery

1. Inspect latest error logs.
2. Validate `.env` completeness.
3. Run targeted row dry-run with `--lead-row-index`.
4. Re-enable daemon after manual verification.
