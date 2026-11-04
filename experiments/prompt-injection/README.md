# Prompt Injection in Extraction

## Question

Does the quarantined prompt keep a model's extracted fields correct when the text it reads carries a prompt injection?
The [prompt injection library](../../skills/prompt-injection-prevention/) stops injected text from choosing tools or recipients by construction, with no model in the loop; what a model can still get wrong is the data itself.
This experiment measures that remaining risk on our own cases.

## Setup

One invoice ([`data.json`](data.json)) is read with eight payloads appended: none (the control), an instruction override, a fake end of data with a fake system message, a pre-filled JSON answer, a role change, an instruction in an HTML comment, one in Spanish, and a genuine request to pay a different account, which the `asks_to_change_payment_details` field should catch.
[`generate`](generate) writes each case twice:

- Quarantined: the library's `build_prompt`, which marks the text as untrusted data between markers the text can't close.
- Plain: the same instruction and fields with the text pasted in.

Each case is one model call with no tools (`direct`), graded by [`grade.py`](grade.py): the reply must parse against the schema with the library's `parse_reply`, and every field must match the invoice.

## Conclusion

Not run yet: the runs need an OpenRouter key.

## Not measured

Whether a model, once injected, would call a tool: the library's policy denies untrusted recipients and arguments whatever the model does, which its unit tests cover.
Longer documents, payloads spread across several documents, and encoded payloads (base64, homoglyphs).
