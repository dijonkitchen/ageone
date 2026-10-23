import pytest

STORIES = [
    "Once upon a time, there was a little cat named Tiny. Tiny liked to play with a ball.",
    "Tom and his dog went to the park. They ran and ran until the sun went down.",
    'Lily said, "I want to help!" Her mom smiled and gave her a big hug.',
    "The bird sang a song. The tree was tall and green, and the sky was blue.",
] * 5


@pytest.fixture
def stories() -> list[str]:
    return STORIES
