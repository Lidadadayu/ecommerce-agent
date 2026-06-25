from __future__ import annotations


def test_agent_presales_smoke():
    from agent.agent import run_agent

    result = run_agent("3000以内推荐一款扫拖一体机器人")

    assert isinstance(result, dict)
    assert result.get("final_answer")
    assert any(word in result["final_answer"] for word in ["扫拖", "机器人", "推荐", "RV"])


def test_agent_fault_smoke():
    from agent.agent import run_agent

    result = run_agent("扫地机器人不回充怎么办")

    assert isinstance(result, dict)
    assert result.get("final_answer")
    assert any(word in result["final_answer"] for word in ["回充", "机器人", "检查", "售后", "基站"])
