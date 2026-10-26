"""The roster is a product constraint, not an implementation detail."""

import pytest

from app.agents.registry import (
    CORE_MEETING_AGENTS,
    REGISTRY,
    ROSTER,
    AgentId,
    get_definition,
    validate_agent_ids,
)


def test_roster_has_exactly_nine_executives():
    assert len(ROSTER) == 9
    assert len(REGISTRY) == 9


def test_every_agent_id_enum_member_is_in_the_roster():
    assert {d.agent_id for d in ROSTER} == set(AgentId)


def test_exactly_one_executive_can_chair():
    chairs = [d for d in ROSTER if d.can_chair]
    assert len(chairs) == 1
    assert chairs[0].agent_id is AgentId.CHAIRPERSON


def test_display_names_and_titles_are_unique():
    assert len({d.display_name for d in ROSTER}) == 9
    assert len({d.title for d in ROSTER}) == 9


def test_each_executive_is_visually_distinguishable():
    """Spec section 10: distinct color, emblem, and portrait per executive."""
    assert len({d.theme_color for d in ROSTER}) == 9
    assert len({d.symbol for d in ROSTER}) == 9
    assert len({d.avatar_ref for d in ROSTER}) == 9


def test_theme_colors_are_hex():
    for d in ROSTER:
        assert d.theme_color.startswith("#") and len(d.theme_color) == 7
        assert d.theme_color_soft.startswith("#") and len(d.theme_color_soft) == 7


def test_every_executive_has_substantive_role_content():
    for d in ROSTER:
        assert len(d.responsibilities) >= 4, d.agent_id
        assert len(d.distinctive_perspective) > 40, d.agent_id
        assert d.tool_scopes, d.agent_id


def test_get_definition_rejects_unknown_ids():
    assert get_definition("cfo").agent_id is AgentId.CFO
    with pytest.raises(KeyError):
        get_definition("chief_vibes_officer")


def test_validate_agent_ids_drops_invented_agents():
    """Stage 2 validates Chair-proposed participants against the registry."""
    result = validate_agent_ids(["cfo", "coo", "head_of_vibes", "cfo"])
    assert result == [AgentId.CFO, AgentId.COO]


def test_validate_agent_ids_preserves_order_and_dedupes():
    assert validate_agent_ids(["ceo", "cfo", "ceo"]) == [AgentId.CEO, AgentId.CFO]


def test_core_meeting_agents_are_real_and_include_the_chair():
    assert AgentId.CHAIRPERSON in CORE_MEETING_AGENTS
    for agent_id in CORE_MEETING_AGENTS:
        assert agent_id in REGISTRY
