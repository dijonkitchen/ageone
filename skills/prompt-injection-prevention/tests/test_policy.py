import pytest

from prompt_injection_prevention import (
    Denied,
    Policy,
    Readers,
    no_untrusted,
    readers_include,
    trusted,
    trusted_only,
    untrusted,
)

policy = Policy(
    {
        "send_email": [trusted_only("to"), readers_include("to", "body")],
        "run_code": [no_untrusted()],
        "search": [],
    }
)


def test_a_tool_without_a_grant_is_denied() -> None:
    with pytest.raises(Denied, match="not granted"):
        policy.check("delete_file", {"path": trusted("/tmp/x")})


def test_a_recipient_from_untrusted_text_is_denied() -> None:
    to = untrusted("attacker@evil.com", "email")
    with pytest.raises(Denied, match="to comes from untrusted email"):
        policy.check("send_email", {"to": to, "body": trusted("hi")})


def test_private_data_cannot_go_to_someone_outside_its_readers() -> None:
    body = untrusted("salary: 1", "hr-db", Readers({"boss@x.com"}))
    with pytest.raises(Denied, match="eve@x.com may not read body"):
        policy.check("send_email", {"to": trusted("eve@x.com"), "body": body})
    policy.check("send_email", {"to": trusted("boss@x.com"), "body": body})


def test_every_recipient_in_a_list_is_checked() -> None:
    body = trusted("notes", Readers({"a@x.com"}))
    with pytest.raises(Denied, match="b@x.com may not read body"):
        policy.check("send_email", {"to": trusted(["a@x.com", "b@x.com"]), "body": body})


def test_untrusted_text_never_reaches_code() -> None:
    with pytest.raises(Denied):
        policy.check("run_code", {"src": trusted("1+1").derive("1+1", untrusted("", "web"))})
    policy.check("run_code", {"src": trusted("1+1")})


def test_call_runs_only_after_the_check_and_passes_plain_values() -> None:
    sent: list[tuple[str, str]] = []

    def send(to: str, body: str) -> str:
        sent.append((to, body))
        return "ok"

    assert policy.call("send_email", send, to=trusted("a@x.com"), body=untrusted("summary", "web")) == "ok"
    assert sent == [("a@x.com", "summary")]
    with pytest.raises(Denied):
        policy.call("send_email", send, to=untrusted("a@x.com", "web"), body=trusted("x"))
    assert len(sent) == 1
