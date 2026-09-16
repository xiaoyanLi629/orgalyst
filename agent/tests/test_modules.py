from bioagent.modules import COUNT, LABEL, MODULES, describe, full, normalize, short

ALL = [full(n) for n, _, _ in MODULES]


def test_registry_consistent():
    assert len(MODULES) == 22 and sum(COUNT.values()) == 224
    assert short("biomni.tool.database") == "database" and full("database") == "biomni.tool.database"


def test_normalize_orders_dedups_and_filters():
    assert normalize(["literature", "biomni.tool.database", "database", "nope"], ALL) == ["biomni.tool.database", "biomni.tool.literature"]
    assert normalize(["genomics"], ["biomni.tool.database"]) == []
    assert normalize([], ALL) == []


def test_describe_lists_loaded_and_unloaded():
    t = describe(["biomni.tool.database"], ALL)
    assert "已加载：数据库查询(database)" in t and "未加载" in t and "文献与网页(literature)" in t
