from pathlib import Path

import pytest

from llm_from_scratch import data


def test_stories_split_on_the_marker_and_drop_blanks() -> None:
    assert data.stories(f"one{data.EOT}\n two \n{data.EOT}\n") == ["one", "two"]


def test_split_is_seeded_and_disjoint() -> None:
    items = [str(i) for i in range(100)]
    train, val = data.split(items, 0.1, seed=3)
    assert (train, val) == data.split(items, 0.1, seed=3)
    assert len(val) == 10
    assert sorted(train + val) == sorted(items)
    assert data.split(items, 0.1, seed=4) != (train, val)


def test_download_rejects_a_file_with_the_wrong_hash(tmp_path: Path) -> None:
    (tmp_path / data.FILE).write_text("not the dataset")
    with pytest.raises(ValueError, match="SHA-256"):
        data.download(tmp_path)
