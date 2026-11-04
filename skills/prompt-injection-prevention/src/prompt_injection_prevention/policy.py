"""Capability checks before a tool call: deny unless a rule for that tool allows the arguments."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from prompt_injection_prevention.values import Value

# A rule looks at a tool's tagged arguments and returns a reason to deny, or None to allow.
Rule = Callable[[str, Mapping[str, Value[Any]]], str | None]


class Denied(Exception):
    """A tool call the policy refused; the call did not run."""

    def __init__(self, tool: str, reason: str) -> None:
        super().__init__(f"{tool}: {reason}")
        self.tool = tool
        self.reason = reason


class Policy:
    """Tools the program may call, each with the rules its arguments must pass.

    A tool with no entry is denied: capabilities are granted, never assumed.
    """

    def __init__(self, tools: Mapping[str, Sequence[Rule]]) -> None:
        self.tools = {name: tuple(rules) for name, rules in tools.items()}

    def check(self, tool: str, args: Mapping[str, Value[Any]]) -> None:
        """Raise Denied unless the tool is granted and every rule allows these arguments."""
        if tool not in self.tools:
            raise Denied(tool, "tool not granted")
        for rule in self.tools[tool]:
            reason = rule(tool, args)
            if reason is not None:
                raise Denied(tool, reason)

    def call(self, tool: str, fn: Callable[..., Any], **args: Value[Any]) -> Any:
        """Check, then call fn with the plain values. The result is not tagged; tag it before reuse."""
        self.check(tool, args)
        return fn(**{name: v.value for name, v in args.items()})


def trusted_only(*params: str) -> Rule:
    """These arguments must come only from trusted sources (for example a recipient or a path)."""

    def rule(tool: str, args: Mapping[str, Value[Any]]) -> str | None:
        for p in params:
            if p in args and not args[p].trusted:
                names = ", ".join(sorted(s.name for s in args[p].sources if not s.trusted))
                return f"{p} comes from untrusted {names}"
        return None

    return rule


def readers_include(recipient: str, *data: str) -> Rule:
    """Every recipient named by `recipient` must be allowed to read each `data` argument."""

    def rule(tool: str, args: Mapping[str, Value[Any]]) -> str | None:
        if recipient not in args:
            return f"missing {recipient}"
        raw = args[recipient].value
        names = [raw] if isinstance(raw, str) else list(raw)
        for d in data:
            if d not in args:
                continue
            for name in names:
                if not args[d].readers.allows(name):
                    return f"{name} may not read {d}"
        return None

    return rule


def no_untrusted() -> Rule:
    """No argument may come from an untrusted source (for tools that run code or spend money)."""

    def rule(tool: str, args: Mapping[str, Value[Any]]) -> str | None:
        for name, v in args.items():
            if not v.trusted:
                return f"{name} comes from an untrusted source"
        return None

    return rule
