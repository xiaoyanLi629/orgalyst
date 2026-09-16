import os

from bioagent.proxy import pid_alive, render_proxy_config, stale_session_files


def test_pid_alive_self_and_dead():
    assert pid_alive(os.getpid())
    assert not pid_alive(2**22 - 1)


def test_stale_session_files_only_dead(tmp_path):
    (tmp_path / str(os.getpid())).write_text("")
    (tmp_path / "99999999").write_text("")
    (tmp_path / "notanumber").write_text("")
    stale = {p.name for p in stale_session_files(tmp_path)}
    assert stale == {"99999999", "notanumber"}


def test_render_proxy_config_rules_and_ports():
    nodes = {"proxies": [{"name": "A", "type": "vless", "server": "1.2.3.4", "port": 443}]}
    cfg = render_proxy_config(
        nodes, port=17890, controller_port=19090, domains=["anthropic.com", "claude.ai"]
    )
    assert cfg["mixed-port"] == 17890 and cfg["bind-address"] == "127.0.0.1"
    assert cfg["allow-lan"] is False
    assert cfg["external-controller"] == "127.0.0.1:19090"
    assert "dns" not in cfg and "tun" not in cfg
    assert cfg["rules"][:2] == ["DOMAIN-SUFFIX,anthropic.com,PROXY", "DOMAIN-SUFFIX,claude.ai,PROXY"]
    assert cfg["rules"][-1] == "MATCH,DIRECT"
    assert cfg["proxy-groups"][0]["name"] == "PROXY"
    assert "A" in cfg["proxy-groups"][1]["proxies"]
