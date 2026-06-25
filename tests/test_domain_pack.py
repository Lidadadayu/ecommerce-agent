from __future__ import annotations


def test_active_domain_config_loads():
    from agent.domain_loader import get_active_domain_config

    domain = get_active_domain_config()

    assert domain.domain_id == "robot_vacuum"
    assert "扫地机器人" in domain.domain_name
    assert domain.products_file.exists()
    assert domain.knowledge_dir.exists()


def test_domain_keywords_available():
    from agent.domain_loader import get_domain_keywords

    product_words = get_domain_keywords("product_words")
    presales_words = get_domain_keywords("presales_words")
    fault_words = get_domain_keywords("fault_words")

    assert "扫地机器人" in product_words
    assert "推荐" in presales_words or "选购" in presales_words
    assert "不回充" in fault_words or "故障" in fault_words
