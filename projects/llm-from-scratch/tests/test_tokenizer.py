from pathlib import Path

from llm_from_scratch import tokenizer
from llm_from_scratch.data import EOT


def test_round_trips_any_text(stories: list[str]) -> None:
    tok = tokenizer.train(EOT.join(stories), 300)
    for text in [
        *stories,
        "snake_case and   spaces\n\n",
        "café ☕ 日本語 ...!?",
        "it's they'll",
        "",
    ]:
        assert tok.decode(tok.encode(text)) == text


def test_end_of_text_is_one_special_token(stories: list[str]) -> None:
    tok = tokenizer.train(EOT.join(stories), 300)
    ids = tok.encode(f"a{EOT}b")
    assert ids.count(tok.eot) == 1
    assert tok.eot == tok.vocab_size - 1


def test_merges_shorten_the_text_and_fill_the_vocabulary(stories: list[str]) -> None:
    text = EOT.join(stories)
    tok = tokenizer.train(text, 320)
    assert tok.vocab_size == 320
    assert len(tok.encode(text)) < len(text.encode()) / 2


def test_training_is_deterministic(stories: list[str]) -> None:
    text = EOT.join(stories)
    assert tokenizer.train(text, 300).merges == tokenizer.train(text, 300).merges


def test_save_and_load(stories: list[str], tmp_path: Path) -> None:
    tok = tokenizer.train(EOT.join(stories), 300)
    tok.save(tmp_path / "tok.json")
    loaded = tokenizer.Tokenizer.load(tmp_path / "tok.json")
    assert loaded.encode(stories[0]) == tok.encode(stories[0])
