#!/usr/bin/env python3
import argparse
import json
import sys
import time
import uuid
import xmlrpc.client
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

GLOBAL_UUID_FIELD = "x_global_uuid"
CONFLICT_LOG = "conflicts.log"


@dataclass
class OdooConfig:
    url: str
    db: str
    username: str
    password: str


class OdooClient:
    def __init__(self, config: OdooConfig):
        self.config = config
        self.common = xmlrpc.client.ServerProxy(f"{config.url}/xmlrpc/2/common")
        self.uid = self.common.authenticate(
            config.db, config.username, config.password, {}
        )
        if not self.uid:
            raise RuntimeError(f"Authentication failed for {config.db} at {config.url}")
        self.models = xmlrpc.client.ServerProxy(f"{config.url}/xmlrpc/2/object")

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        return self.models.execute_kw(
            self.config.db, self.uid, self.config.password, model, method, args, kwargs
        )


def load_config(path: Path) -> Tuple[OdooConfig, List[OdooConfig], Dict[str, Any]]:
    data = yaml.safe_load(path.read_text())
    primary = OdooConfig(**data["primary"])
    targets = [OdooConfig(**target) for target in data.get("targets", [])]
    sync = data.get("sync", {})
    return primary, targets, sync


def load_state(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_state(path: Path, state: Dict[str, str]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def ensure_global_uuid_field(client: OdooClient) -> None:
    field_ids = client.execute(
        "ir.model.fields",
        "search",
        [["name", "=", GLOBAL_UUID_FIELD], ["model", "=", "res.partner"]],
        {"limit": 1},
    )
    if field_ids:
        return
    client.execute(
        "ir.model.fields",
        "create",
        {
            "name": GLOBAL_UUID_FIELD,
            "field_description": "Global UUID",
            "model_id": client.execute(
                "ir.model",
                "search",
                [["model", "=", "res.partner"]],
                {"limit": 1},
            )[0],
            "ttype": "char",
            "required": False,
            "readonly": False,
            "store": True,
            "size": 36,
        },
    )


def normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def fetch_recent_contacts(
    client: OdooClient, fields: List[str], since: Optional[str], limit: int
) -> List[Dict[str, Any]]:
    domain = []
    if since:
        domain = [["write_date", ">", since]]
    return client.execute(
        "res.partner",
        "search_read",
        domain,
        {
            "fields": fields,
            "limit": limit,
            "order": "write_date asc",
        },
    )


def find_match(
    target: OdooClient, contact: Dict[str, Any]
) -> Tuple[Optional[int], Optional[str]]:
    global_id = contact.get(GLOBAL_UUID_FIELD)
    if global_id:
        ids = target.execute(
            "res.partner", "search", [[GLOBAL_UUID_FIELD, "=", global_id]]
        )
        if ids:
            return ids[0], "global_uuid"

    email = normalize_email(contact.get("email"))
    if email:
        ids = target.execute("res.partner", "search", [["email", "=", email]])
        if len(ids) == 1:
            return ids[0], "email"
        if len(ids) > 1:
            return None, "conflict_email"

    phone = normalize_phone(contact.get("phone")) or normalize_phone(contact.get("mobile"))
    if phone:
        ids = target.execute(
            "res.partner",
            "search",
            ["|", ["phone", "=", phone], ["mobile", "=", phone]],
        )
        if len(ids) == 1:
            return ids[0], "phone"
        if len(ids) > 1:
            return None, "conflict_phone"

    return None, None


def log_conflict(target_name: str, contact: Dict[str, Any], reason: str) -> None:
    with Path(CONFLICT_LOG).open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "target": target_name,
                    "reason": reason,
                    "contact": contact,
                }
            )
            + "\n"
        )


def prepare_payload(contact: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    payload = {field: contact.get(field) for field in fields if field in contact}
    payload[GLOBAL_UUID_FIELD] = contact.get(GLOBAL_UUID_FIELD) or str(uuid.uuid4())
    return payload


def sync_contact(
    source_contact: Dict[str, Any],
    target: OdooClient,
    target_name: str,
    fields: List[str],
) -> None:
    payload = prepare_payload(source_contact, fields)
    match_id, reason = find_match(target, payload)
    if reason and reason.startswith("conflict"):
        log_conflict(target_name, payload, reason)
        return
    if match_id:
        target.execute("res.partner", "write", [match_id], payload)
    else:
        target.execute("res.partner", "create", payload)


def sync_contacts(
    primary: OdooClient,
    targets: List[Tuple[str, OdooClient]],
    fields: List[str],
    state_path: Path,
    batch_size: int,
) -> None:
    state = load_state(state_path)
    since = state.get("primary_write_date")
    contacts = fetch_recent_contacts(primary, fields + [GLOBAL_UUID_FIELD], since, batch_size)

    if not contacts:
        return

    for contact in contacts:
        if not contact.get(GLOBAL_UUID_FIELD):
            contact[GLOBAL_UUID_FIELD] = str(uuid.uuid4())
            primary.execute(
                "res.partner", "write", [contact["id"]], {GLOBAL_UUID_FIELD: contact[GLOBAL_UUID_FIELD]}
            )
        for target_name, target in targets:
            sync_contact(contact, target, target_name, fields)

    last_write_date = contacts[-1].get("write_date")
    if last_write_date:
        state["primary_write_date"] = last_write_date
        save_state(state_path, state)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Odoo contacts from primary to targets")
    parser.add_argument("--config", required=True, type=Path, help="Path to config.yaml")
    parser.add_argument(
        "--state",
        default=Path("state.json"),
        type=Path,
        help="Path to sync state file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    primary_config, target_configs, sync = load_config(args.config)

    fields = sync.get("fields", [])
    if "write_date" not in fields:
        fields.append("write_date")

    batch_size = int(sync.get("batch_size", 200))

    primary = OdooClient(primary_config)
    ensure_global_uuid_field(primary)

    targets: List[Tuple[str, OdooClient]] = []
    for target in target_configs:
        client = OdooClient(target)
        ensure_global_uuid_field(client)
        targets.append((target.db, client))

    sync_contacts(primary, targets, fields, args.state, batch_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
