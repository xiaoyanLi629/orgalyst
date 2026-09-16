from bioagent.commands import parse_command


def test_plain_text_is_not_command():
    assert parse_command("hello /new") is None
    assert parse_command("  ") is None


def test_parses_name_and_arg():
    c = parse_command("/model claude-opus-5")
    assert c.name == "model" and c.arg == "claude-opus-5"
    assert parse_command("/quit").arg == ""
    assert parse_command("/exit").name == "quit"
    assert parse_command("/cd /tmp/x y").arg == "/tmp/x y"


def test_memory_command():
    assert parse_command("/memory").name == "memory"
    assert parse_command("/memory clear").arg == "clear"


def test_unknown_command_returns_help():
    assert parse_command("/wat").name == "help"
