"""Rules for restart_pod. kube-system is always refused."""

FORBIDDEN_NAMESPACES = frozenset({"kube-system"})


def parse_allowlist(raw: str) -> set[str]:
    return {item.strip() for item in (raw or "").split(",") if item.strip()}


def namespace_allowed(namespace: str, allowlist: set[str]) -> bool:
    if namespace in FORBIDDEN_NAMESPACES:
        return False
    if allowlist and namespace not in allowlist:
        return False
    return True


def cooldown_remaining(last_epoch: float | None, now_epoch: float, cooldown_seconds: int) -> int:
    if last_epoch is None or cooldown_seconds <= 0:
        return 0
    left = int(cooldown_seconds - (now_epoch - last_epoch))
    return max(0, left)
