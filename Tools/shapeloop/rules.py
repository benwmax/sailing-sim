"""Object-name rules shared by the shape loop's plain-Python tools (common.py holds the same for Blender's side)."""


def base_name(name):
    """Blender's duplicate suffix (.001) dropped; names like KeelNut_0_-0.06 keep their own dots."""
    head, dot, tail = name.rpartition(".")
    return head if dot and len(tail) == 3 and tail.isdigit() else name


def matches(name, rule):
    """A rule ending in '_' or '*' is a prefix ('*' dropped); any other rule is an exact name."""
    base = base_name(name)
    if rule.endswith("*"):
        return base.startswith(rule[:-1])
    if rule.endswith("_"):
        return base.startswith(rule)
    return base == rule
