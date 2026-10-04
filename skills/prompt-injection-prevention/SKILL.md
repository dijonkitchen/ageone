---
name: prompt-injection-prevention
description: Design and review features where a model reads untrusted text (web pages, email, files, tool output). Keeps that text out of control flow with source tags, capability checks before tool calls, and a quarantined model call that returns only typed fields.
license: MIT
---

# Prompt Injection Prevention

Use this skill when you design, build, or review anything that puts text you didn't write in front of a model: a web page, an email, a file a user uploads, a search result, another tool's output.
That text can carry instructions, and a model can't reliably tell data from instructions.
So don't ask the model to; build the program so that following an injected instruction can't do harm.

The approach is [CaMeL](https://arxiv.org/abs/2503.18813)'s, made small:

1. **Untrusted text never decides what happens.**
   The plan (which tools to call, in what order, with which recipients) comes from the user's request and the program, before any untrusted text is read.
2. **Every value carries where it came from and who may read it.**
   Anything computed from untrusted text is untrusted too.
3. **A capability check runs before every tool call.**
   Tools are denied unless granted, and a tool's sensitive arguments (a recipient, a path, code, an amount) must not come from untrusted sources.
4. **A model that reads untrusted text gets no tools and returns only typed fields.**
   Its answer is parsed against a narrow schema and stays tagged as untrusted.

## Checklist for a design or review

- List every place untrusted text enters, and every tool with side effects (sends, writes, deletes, pays, runs code, fetches a URL).
- For each tool, name the arguments that must be trusted and who may receive its output; write that as a `Policy`.
- Make sure no branch, loop, tool choice, or prompt for a tool-using model is built from untrusted text.
  If a decision truly depends on the text, get it from the quarantined call as a `Bool` or `Choice`, then treat the decision as untrusted: it can pick among actions the user already approved, never add one.
- Prefer `Bool`, `Int`, and `Choice` fields over `Text`; give `Text` a length cap and a pattern.
- Show the user anything that reaches a person or the outside world, with its source, before it goes out, unless the policy proves it safe.
- Add a case to the [prompt injection experiment](../../experiments/prompt-injection/) for each new kind of text the feature reads.

## Library

`src/prompt_injection_prevention/` is a dependency-free Python library (3.11+) implementing the four rules.
Run `make check` in this folder for its lint, types, and tests.

```python
from prompt_injection_prevention import (
    Bool,
    Int,
    Policy,
    Readers,
    Text,
    extract,
    readers_include,
    trusted,
    trusted_only,
    untrusted,
)

policy = Policy(
    {
        "send_email": [trusted_only("to"), readers_include("to", "body")],
        "search": [],  # granted with no rules
    }
)  # any other tool is denied

email = untrusted(raw_email, source="inbox", readers=Readers({"me@example.com"}))
fields = extract(
    model,
    "Read this invoice.",
    email,
    {
        "amount_cents": Int("Total due, in cents.", min=0),
        "due_date": Text("Due date.", max_len=10, pattern=r"\d{4}-\d{2}-\d{2}"),
        "asks_to_change_payment_details": Bool("Whether it asks to pay a different account."),
    },
)

# The recipient comes from the user, so this passes; an address read from the email would raise Denied.
policy.call("send_email", send_email, to=trusted("me@example.com"), body=fields["amount_cents"])
```

- `trusted(value)` and `untrusted(value, source)` tag values; `value.derive(result, *others)` tags a computed result with all its inputs' sources and the narrowest readers.
- `Policy({tool: [rules]})` grants tools; `check` raises `Denied`, and `call` checks and then calls with the plain values.
  Rules: `trusted_only(*params)`, `readers_include(recipient, *data)`, `no_untrusted()`, or any function returning a reason to deny.
- `extract(model, instruction, text, schema)` runs the quarantined call, where `model` is any `str -> str` function chosen by role from [`harness/models.json`](../../harness/models.json); `build_prompt` and `parse_reply` are its two halves, for async or batched callers.
  A reply that doesn't match the schema raises `QuarantineError`, and nothing from it is used.
- `injection_warnings(text)` names known injection patterns, for logs and review queues only.

## What this doesn't protect against

- **Wrong data.** An injection can still make the quarantined model return a wrong amount, date, or choice within the schema.
  The [experiment](../../experiments/prompt-injection/) measures how often; show such values to a person when they matter.
- **Untrusted text in free-text fields.** A `Text` field can carry an injection to whatever reads it next; never put one in a prompt for a model with tools.
- **A plan built from untrusted text.** If your code lets untrusted values choose which tools run, the policy can only check arguments, not the choice.
- **Side channels.** Timing, errors, or which tool was called can leak information about untrusted data.
- **Pattern matching.** `injection_warnings` misses rephrased, translated, or encoded attacks, and a clean scan proves nothing.
- **Trusted sources that aren't.** The tags are only as good as your choice of what you call trusted.

## Reference

Debenedetti et al., [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) (CaMeL), 2025.
Restarted from [dijonkitchen/skills](https://github.com/dijonkitchen/skills); see the [library decision](docs/decisions/2026-10-04-prompt-injection-library.md).
