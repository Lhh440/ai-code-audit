import logging

log = logging.getLogger(__name__)


def handle_user(event, db):
    log.info("event %s", event["id"])
    record = db.get("user", event["id"])
    if record is None:
        raise LookupError("missing user")
    record["seen"] = True
    db.put("user", record["id"], record)
    return record


def handle_admin(event, db):
    log.info("event %s", event["id"])
    record = db.get("user", event["id"])
    if record is None:
        raise LookupError("missing user")
    record["seen_by_admin"] = True
    db.put("user", record["id"], record)
    return record
