"""Finite workflow recipes. Conditions are data, never Python expressions."""

import re

FIELDS = {"task.complexity", "policy.requires_review", "task.cross_repo", "task.investigation", "task.high_risk"}
STATES = {"pending", "ready", "running", "succeeded", "failed", "blocked", "skipped", "cancelled"}
TERMINAL = {"succeeded", "failed", "blocked", "skipped", "cancelled"}


def _lookup(context, field):
    if field not in FIELDS:
        raise ValueError(f"unsupported condition field: {field}")
    value = context
    for key in field.split("."):
        value = value.get(key, {}) if isinstance(value, dict) else None
    if isinstance(value, dict):
        raise ValueError(f"condition context missing: {field}")
    return value


def condition(rule, context):
    if rule is None:
        return True
    if isinstance(rule, bool):
        return rule
    if isinstance(rule, str):
        if rule == "always":
            return True
        if rule == "nontrivial":
            return _lookup(context, "task.complexity") != "trivial"
        if rule == "requires_review":
            return _lookup(context, "policy.requires_review") is True
        if rule == "high_risk":
            return _lookup(context, "task.high_risk") is True
        if rule in FIELDS:
            value = _lookup(context, rule)
            if not isinstance(value, bool):
                raise ValueError("boolean condition requires boolean context")
            return value
        match = re.fullmatch(r"(task\.complexity)\s*(==|!=)\s*'([a-z_-]+)'", rule)
        if not match:
            raise ValueError(f"unsupported condition: {rule}")
        same = _lookup(context, match[1]) == match[3]
        return same if match[2] == "==" else not same
    if isinstance(rule, dict) and set(rule) == {"field", "equals"}:
        return _lookup(context, rule["field"]) == rule["equals"]
    if isinstance(rule, dict) and set(rule) == {"field", "not_equals"}:
        return _lookup(context, rule["field"]) != rule["not_equals"]
    if isinstance(rule, dict) and set(rule) == {"field", "in"} and isinstance(rule["in"], list):
        return _lookup(context, rule["field"]) in rule["in"]
    raise ValueError("invalid finite workflow condition")


def validate_recipe(recipe):
    if not isinstance(recipe, dict) or not isinstance(recipe.get("stages"), list) or not recipe["stages"]:
        raise ValueError("recipe requires nonempty stages")
    stages = recipe["stages"]
    ids = [s.get("id") for s in stages]
    if any(not isinstance(i, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", i) for i in ids):
        raise ValueError("invalid stage ID")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate stage ID")
    graph = {}
    for stage in stages:
        needs = stage.get("needs", [])
        if not isinstance(needs, list) or any(not isinstance(n, str) for n in needs):
            raise ValueError("needs must be stage names")
        graph[stage["id"]] = [n.rstrip("?") for n in needs]
        if any(n not in ids or n == stage["id"] for n in graph[stage["id"]]):
            raise ValueError("unknown or self dependency")
        # Validate syntax using a representative context, never eval arbitrary expressions.
        condition(stage.get("when"), {"task": {"complexity": "trivial", "cross_repo": False,
                                              "investigation": False, "high_risk": False},
                                     "policy": {"requires_review": True}})
    seen, active = set(), set()

    def visit(node):
        if node in active:
            raise ValueError("workflow dependency cycle")
        if node in seen:
            return
        active.add(node)
        for dependency in graph[node]:
            visit(dependency)
        active.remove(node)
        seen.add(node)

    for node in graph:
        visit(node)
    return recipe


def readiness(needs, statuses):
    """Optional dependencies permit skipped nodes, never failed checks."""
    for dependency in needs:
        optional = dependency.endswith("?")
        state = statuses.get(dependency.rstrip("?"))
        if state in {"failed", "blocked", "cancelled"}:
            return "blocked"
        if state == "skipped" and not optional:
            return "blocked"
        if state != "succeeded" and not (optional and state == "skipped"):
            return "pending"
    return "ready"
