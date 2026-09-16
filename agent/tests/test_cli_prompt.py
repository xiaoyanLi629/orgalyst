from bioagent.cli import build_system_prompt
from bioagent.config import BiomniSettings, ProxySettings, Settings


def test_system_prompt_includes_name_and_project_file(tmp_path):
    (tmp_path / "BIOAGENT.md").write_text("# 项目知识\n样本 LU-554 是肺癌类器官")
    s = Settings(
        root=tmp_path, assistant_name="BioAgent", model="m", cwd=tmp_path,
        readonly_dirs=[tmp_path / "raw"], daily_cost_cap_usd=1, api_key="k",
        proxy=ProxySettings(), biomni=BiomniSettings(),
    )
    p = build_system_prompt(s)
    assert "BioAgent" in p and "LU-554" in p and str(tmp_path / "raw") in p and "中文" in p


def test_system_prompt_includes_user_memory(tmp_path):
    s = Settings(
        root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[],
        daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(), biomni=BiomniSettings(), user="zhangsan",
    )
    p = build_system_prompt(s)
    assert "还没有记忆" in p and str(s.memory_file) in p
    s.memory_file.parent.mkdir(parents=True)
    s.memory_file.write_text("- 2026-09-07 负责 LU-554 的分割评估")
    assert "LU-554" in build_system_prompt(s)
    # 超长截断
    s.memory.max_chars = 10
    assert "已截断" in build_system_prompt(s)


def test_system_prompt_without_project_file(tmp_path):
    s = Settings(
        root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[],
        daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(), biomni=BiomniSettings(),
    )
    assert "X" in build_system_prompt(s)


def test_system_prompt_mentions_files_and_outputs(tmp_path):
    s = Settings(root=tmp_path, assistant_name="X", model="m", cwd=tmp_path / "out", readonly_dirs=[],
                 daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(), biomni=BiomniSettings(), user="u")
    p = build_system_prompt(s)
    assert str(s.store.files_dir) in p and str(tmp_path / "out") in p
