from __PACKAGE__ import greet


def test_greet_names_who_it_greets() -> None:
    assert greet("ageone") == "Hello, ageone!"
