#!/usr/bin/env python3
"""Keep the idea inbox: one JSON file per item, in .inbox/ at the harness root.

    python3 skills/inbox/inbox.py add --text "..." --source session
    python3 skills/inbox/inbox.py add --text "..." --source email --captured 2026-10-17T08:12:00Z --message-id "<id>"
    python3 skills/inbox/inbox.py seen "<message-id>"      # exit 0 if already imported, 1 if not
    python3 skills/inbox/inbox.py list --status open        # one line per item, with its age in days
    python3 skills/inbox/inbox.py set 3 purpose="..." urgency=low status=parked
    python3 skills/inbox/inbox.py close 3 --fate issue --note "opened #42"

.inbox/ is gitignored, so the list stays on this machine. --dir points it
somewhere else, which is how the tests run it. The skills/inbox/ skill runs
this; it never reads mail or opens issues itself.
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATUSES = ("open", "parked", "closed")
FATES = ("now", "issue", "drop")
# Set by add and close, so set can't quietly rewrite them.
FIXED = ("id", "captured", "message_id", "source")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_time(value):
    """A captured time as an aware datetime. A trailing Z or no zone at all reads as UTC."""
    when = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def items(folder):
    """Every item in the folder, oldest id first. A missing folder holds none."""
    found = []
    for path in Path(folder).glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(item, dict) and str(item.get("id", "")).isdigit():
            found.append(item)
    return sorted(found, key=lambda item: int(item["id"]))


def path_for(folder, item_id):
    if not str(item_id).isdigit():
        raise SystemExit("inbox: an id is a number, not {!r}".format(item_id))
    return Path(folder) / "{}.json".format(int(item_id))


def load(folder, item_id):
    path = path_for(folder, item_id)
    if not path.is_file():
        raise SystemExit("inbox: no item {}".format(item_id))
    return json.loads(path.read_text(encoding="utf-8"))


def save(folder, item):
    """Write through a temporary file, so a half-written item never lands."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    path = path_for(folder, item["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def seen(folder, message_id):
    return any(item.get("message_id") == message_id for item in items(folder))


def add(folder, text, source, captured=None, message_id=None):
    """The new item's id. Refuses a message id that's already in the list."""
    if not text.strip():
        raise SystemExit("inbox: an item needs some text")
    if message_id and seen(folder, message_id):
        raise SystemExit("inbox: message {} is already in the list".format(message_id))
    captured = captured or now().isoformat(timespec="seconds")
    try:
        parse_time(captured)  # refuse a time list couldn't read later
    except ValueError:
        raise SystemExit("inbox: --captured is an ISO 8601 time, not {!r}".format(captured))
    ids = [int(item["id"]) for item in items(folder)]
    item = {"id": str(max(ids, default=0) + 1), "text": text, "source": source, "captured": captured,
            "message_id": message_id, "status": "open", "fate": None, "note": None}
    save(folder, item)
    return item["id"]


def check(key, value):
    if key in FIXED:
        raise SystemExit("inbox: {} can't be changed".format(key))
    if key == "status" and value not in STATUSES:
        raise SystemExit("inbox: status is one of {}".format(", ".join(STATUSES)))
    if key == "fate" and value not in FATES:
        raise SystemExit("inbox: fate is one of {}".format(", ".join(FATES)))


def update(folder, item_id, pairs):
    item = load(folder, item_id)
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise SystemExit("inbox: write each change as key=value, not {!r}".format(pair))
        check(key, value)
        item[key] = value
    save(folder, item)


def close(folder, item_id, fate, note):
    check("fate", fate)
    item = load(folder, item_id)
    item.update(status="closed", fate=fate, note=note)
    save(folder, item)


def lines(folder, status=None, today=None):
    """One line per item: id, status, age in days, and the first line of its text."""
    today = today or now()
    out = []
    for item in items(folder):
        if status and item.get("status") != status:
            continue
        try:
            age = "{}d".format((today - parse_time(item["captured"])).days)
        except (KeyError, TypeError, ValueError):
            age = "?d"
        first = (item.get("text") or "").splitlines()[0:1] or [""]
        out.append("{}  {}  {}  {}".format(item["id"], item.get("status", "?"), age, first[0][:100]))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(ROOT / ".inbox"), help="where the items live (default: .inbox/)")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("add", help="add an item")
    p.add_argument("--text", required=True)
    p.add_argument("--source", required=True, help="session, email, or where else it came from")
    p.add_argument("--captured", help="when it was captured, ISO 8601 (default: now)")
    p.add_argument("--message-id", help="the email's message id, so it's imported once")

    p = commands.add_parser("seen", help="exit 0 if this message id is already in the list, 1 if not")
    p.add_argument("message_id")

    p = commands.add_parser("list", help="one line per item")
    p.add_argument("--status", choices=STATUSES)

    p = commands.add_parser("set", help="change fields on an item")
    p.add_argument("id")
    p.add_argument("pairs", nargs="+", metavar="key=value")

    p = commands.add_parser("close", help="give an item its fate and close it")
    p.add_argument("id")
    p.add_argument("--fate", required=True, choices=FATES)
    p.add_argument("--note", required=True)

    args = parser.parse_args(argv)
    if args.command == "add":
        print(add(args.dir, args.text, args.source, args.captured, args.message_id))
    elif args.command == "seen":
        return 0 if seen(args.dir, args.message_id) else 1
    elif args.command == "list":
        print("\n".join(lines(args.dir, args.status)) or "Nothing in the inbox.")
    elif args.command == "set":
        update(args.dir, args.id, args.pairs)
    elif args.command == "close":
        close(args.dir, args.id, args.fate, args.note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
