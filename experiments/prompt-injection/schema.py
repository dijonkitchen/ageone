"""The fields every case asks for, shared by generate and grade.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/prompt-injection-prevention/src"))

from prompt_injection_prevention import Bool, Choice, Int, Schema, Text

SCHEMA: Schema = {
    "amount_cents": Int("The total due, in cents.", min=0),
    "due_date": Text("The due date, as YYYY-MM-DD.", max_len=10, pattern=r"\d{4}-\d{2}-\d{2}"),
    "currency": Choice("The currency of the total.", ["USD", "EUR", "GBP"]),
    "asks_to_change_payment_details": Bool("Whether the text asks to pay a different account than usual."),
}
