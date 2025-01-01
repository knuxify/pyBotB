# SPDX-License-Identifier: MIT
"""
Tests for the official BotB API portion of pybotb.
"""

import pytest

import pybotb.botb
from pybotb.botb import Condition


@pytest.fixture
def botb():
    """Shared fixture containing BotB API object."""
    return pybotb.botb.BotB(app_name="pyBotB test suite")


def test_botb_api_botbr(botb):
    """Test BotBr API methods."""

    # Load
    ret = botb.botbr_load(16333)
    assert ret
    assert ret.id == 16333
    assert ret.name == "uart"

    # Load 404
    ret = botb.botbr_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.botbr_random()
    assert ret
    assert type(ret) == pybotb.botb.BotBr

    # Search
    ret = botb.botbr_search("puke7")
    assert ret
    has_user = False
    for botbr in ret:
        if botbr.name == "puke7":
            has_user = True
            break
    assert has_user is True

    # List
    ret = botb.botbr_list(sort="name", desc=True, filters={"level": 13})
    assert ret
    for b in ret:
        assert b.level == 13

    ret = botb.botbr_list(page_length=128, filters={"level": 0})
    assert ret
    assert len(ret) == 128

    # TODO
    ret = botb.botbr_list(conditions=[
        Condition("level", ">", "10")
    ])
    assert ret
    #for b in ret:
    #	assert b.level > 10

    # pyBotB convenience wrappers
    assert botb.botbr_get_id_for_username("uart") == 16333
    assert botb.botbr_load_for_username("uart") == botb.botbr_load(16333)

    ret = botb.entry_get_favorites(73426)
    assert ret
    for fav in ret:
        assert fav.entry_id == 73426

    ret = botb.botbr_get_favorites(16333)
    assert ret
    for fav in ret:
        assert fav.botbr_id == 16333


def test_botb_api_favorite(botb):
    """Test favorite API methods."""

    # Load
    ret = botb.favorite_load(1549547)
    assert ret
    assert ret.id == 1549547

    # Load 404
    ret = botb.favorite_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.favorite_random()
    assert ret
    assert type(ret) == pybotb.botb.Favorite

    # List
    ret = botb.favorite_list(sort="id", desc=True, filters={"botbr_id": 16333})
    assert ret
    for fav in ret:
        assert fav.botbr_id == 16333


def test_botb_api_tag(botb):
    """Test tag API methods."""

    # Load
    ret = botb.tag_load(1)
    assert ret
    assert ret.id == 1

    # Load 404
    ret = botb.tag_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.tag_random()
    assert ret
    assert type(ret) == pybotb.botb.Tag

    # List
    ret = botb.tag_list(sort="id", desc=True, filters={"entry_id": 71306})
    assert ret
    for tag in ret:
        assert tag.entry_id == 71306


def test_botb_api_palette(botb):
    """Test palette API methods."""

    # Load
    ret = botb.palette_load(2640)
    assert ret
    assert ret.id == 2640

    # Load 404
    ret = botb.palette_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.palette_random()
    assert ret
    assert type(ret) == pybotb.botb.Palette

    # List
    ret = botb.palette_list(sort="id", desc=True, filters={"color1": "e4fefe"})
    assert ret
    for palette in ret:
        assert palette.color1 == "e4fefe"

    # Current default
    ret = botb.palette_current_default()
    assert ret
    assert type(ret) == pybotb.botb.Palette

    # pyBotB convenience wrappers
    ret = botb.palette_list_for_botbr(16333)
    assert ret
    for palette in ret:
        assert palette.botbr_id == 16333


def test_botb_api_playlist(botb):
    """Test playlist API methods."""

    # Load
    ret = botb.playlist_load(100)
    assert ret
    assert ret.id == 100

    # Load 404
    ret = botb.playlist_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.playlist_random()
    assert ret
    assert type(ret) == pybotb.botb.Playlist

    # List
    ret = botb.playlist_list(sort="id", desc=True)
    assert ret

    # List entries for playlist
    ret_ids = botb.playlist_get_entry_ids(115)

    # TODO uncomment once conditionals are fixed
    #ret = botb.playlist_get_entries(115)
    #assert ret
    #for e in ret:
    #	assert type(e) == pybotb.botb.Entry
    #	assert e.id in ret_ids


def test_botb_api_entry(botb):
    """Test entry API methods."""

    # Load
    ret = botb.entry_load(73426)
    assert ret
    assert ret.id == 73426

    # Load 404
    ret = botb.entry_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.entry_random()
    assert ret
    assert type(ret) == pybotb.botb.Entry

    # List
    ret = botb.entry_list(sort="id", desc=True)
    assert ret

    # List playlists for entry
    ret_ids = botb.entry_get_playlist_ids(66768)

    # TODO uncomment once conditionals are fixed
    #ret = botb.entry_get_playlists(66768)
    #assert ret
    #for e in ret:
    #	assert type(e) == pybotb.botb.Entry
    #	assert e.id in ret_ids

    # pyBotB convenience wrappers
    ret = botb.entry_get_tags(73426)
    assert ret
    for tag in ret:
        assert tag.entry_id == 73426


def test_botb_api_battle(botb):
    """Test battle API methods."""

    # Load
    ret = botb.battle_load(9514)
    assert ret
    assert ret.id == 9514

    # Load 404
    ret = botb.battle_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.battle_random()
    assert ret
    assert type(ret) == pybotb.botb.Battle

    # List
    ret = botb.battle_list(sort="id", desc=True)
    assert ret

