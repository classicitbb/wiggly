# Odoo Contact Sync (Option B)

This project provides a simple **Option B** sync flow: contacts are created/updated in a
**primary Odoo database**, and a sync script propagates those changes to **secondary
Odoo databases**. The script also attempts to deduplicate by using a shared
`x_global_uuid` custom field, and falls back to email/phone matching when needed.

## Features
- One-way sync from a primary Odoo DB to multiple targets.
- Deduplication based on:
  1. `x_global_uuid` (preferred)
  2. normalized email
  3. normalized phone
- Conflict detection for ambiguous matches.
- State file to sync only recent changes.

## Setup

1. Create and populate a configuration file:

```bash
cp config.example.yaml config.yaml
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the sync:

```bash
python sync_contacts.py --config config.yaml --state state.json
```

## Files
- `sync_contacts.py`: main sync script.
- `config.example.yaml`: sample configuration.
- `state.json`: stored sync cursor (created automatically).
- `conflicts.log`: detected ambiguous matches.

## Notes
- The script will ensure the `x_global_uuid` field exists on `res.partner`.
- For intervention, review `conflicts.log` and correct/merge in Odoo, then re-run.
