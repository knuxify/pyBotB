# SPDX-License-Identifier: MIT
"""Tests for the official BotB API portion of pybotb."""

from datetime import date as dt_date
import pytest

import pybotb.botb
from pybotb.botb import Condition
import pybotb.types


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
    assert type(ret) is pybotb.types.BotBr

    # Search
    ret = [b for b in botb.botbr_search("puke7")]
    assert ret
    has_user = False
    for botbr in ret:
        if botbr.name == "puke7":
            has_user = True
            break
    assert has_user is True

    # List
    ret = [
        b
        for b in botb.botbr_list(
            sort="name", desc=True, filters={"level": 13}, max_items=50
        )
    ]
    assert ret
    for b in ret:
        assert b.level == 13

    ret = [b for b in botb.botbr_list(filters={"level": 0}, max_items=128)]
    assert ret
    assert len(ret) == 128

    ret = [
        b
        for b in botb.botbr_list(
            conditions=[Condition("level", ">", "10")], max_items=50
        )
    ]
    assert ret
    for b in ret:
        assert b.level > 10

    # Get entries
    ret = [b for b in botb.botbr_get_entries(16333, sort="id", max_items=50)]
    assert ret[0].id == 70736

    # pyBotB convenience wrappers
    assert botb.botbr_levels[0] == 0

    assert botb.botbr_get_id_for_username("uart") == 16333

    # HACK: Boon count can (and does) change between the two requests, so we
    # manually override it here to prevent false failures.
    ret1 = botb.botbr_load_for_username("uart")
    ret1.boons = 0
    ret2 = botb.botbr_load(16333)
    ret2.boons = 0
    assert ret1 == ret2

    # Get favorite entries
    ret = botb.botbr_get_favorite_entries(16333, max_items=50)
    for b in ret:
        assert type(b) is pybotb.types.Entry

    # Get palettes
    ret = botb.botbr_get_palettes(16333)
    assert ret
    for palette in ret:
        assert palette.botbr_id == 16333

    # Get badge progress
    ret = botb.botbr_get_badge_progress(16333)
    assert ret
    assert ret["s3xmodit"] > 15

    # Get tags given
    ret = botb.botbr_get_tags_given(9635)
    assert len(ret) > 0

    ret = botb.botbr_get_tags_given(16352)
    assert len(ret) == 0

    # Get tags received
    ret = botb.botbr_get_tags_received(9635)
    assert len(ret) > 0

    ret = botb.botbr_get_tags_received(16352)
    assert len(ret) == 0

    # Get avatars
    ret = botb.botbr_get_avatars(16333)
    assert len(ret) > 0

    # Get battles hosted
    ret = [b for b in botb.botbr_get_battles_hosted(9635, max_items=25)]
    assert len(ret) == 25
    for b in ret:
        assert type(b) is pybotb.types.Battle

    # Get country code
    ret = botb.botbr_get_country_code(16352)
    assert ret == "id"

    ret = botb.botbr_get_country_code(123456787654321)
    assert ret is None


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
    assert type(ret) is pybotb.types.Battle

    # List
    ret = [b for b in botb.battle_list(sort="id", desc=True, max_items=50)]
    assert ret

    # Current battles
    ret = botb.battle_current()
    for b in ret:
        assert type(b) is pybotb.types.Battle

    # List by date
    ret = botb.battle_list_by_date("2024-04-20")
    for b in ret:
        assert type(b) is pybotb.types.Battle

    assert set([b1.id for b1 in ret]) == set(
        [b2.id for b2 in botb.battle_list_by_date(dt_date(year=2024, month=4, day=20))]
    )

    ret = botb.battle_list_by_month("2024-04")
    for b in ret:
        assert type(b) is pybotb.types.Battle

    # pyBotB methods

    # Get battle description
    ret = botb.battle_get_description(9775)
    assert (
        ret
        == '\n<span class="tb5">write a \r<br/>\nwalkthrough \r<br/>\nfor a fictional \r<br/>\nvideo game!</span> <br/>\n<br/>\n<b><a href="https://battleofthebits.com/arena/Entry/WALKTHROUGH/71049/">original concept by lumiscosity</a></b>\n'
    )

    ret = botb.battle_get_description(9000)
    assert ret is None

    # Get voting categories
    ret = botb.battle_get_voting_categories(9615)
    assert ret == [
        "snowyness",
        "decorativity",
        "yum factor",
        "adventism",
        "candlelight in pants",
    ]

    ret = botb.battle_get_voting_categories(9000)
    assert ret is None

    # Get bitpacks
    ret = botb.battle_get_bitpacks(9615)
    assert len(ret) == 24

    ret = botb.battle_get_bitpacks(9696)
    assert len(ret) == 0

    ret = botb.battle_get_bitpacks(9680)
    assert len(ret) == 1

    ret = botb.battle_get_bitpacks(9587)
    assert len(ret) == 1

    ret = botb.battle_get_bitpacks(2151)
    assert len(ret) == 1


def test_botb_api_entry(botb):
    """Test entry API methods."""
    # Load
    ret = botb.entry_load(73426)
    assert ret
    assert ret.id == 73426
    assert type(ret.botbr) is pybotb.types.BotBr
    assert type(ret.format) is pybotb.types.Format
    for a in ret.authors:
        assert type(a) is pybotb.types.EntryAuthor

    # Load 404
    ret = botb.entry_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.entry_random()
    assert ret
    assert type(ret) is pybotb.types.Entry

    # List
    ret = [e for e in botb.entry_list(sort="id", desc=True, max_items=50)]
    assert ret

    # List with conditions
    ret = botb.entry_list(
        conditions=[
            Condition("id", ">", 5),
            Condition("donloads", "<", 10),
        ],
    )
    for entry in ret:
        assert entry.id > 5
        assert entry.donloads < 10

    # Note - this test may be flaky if the conditions aren't right.
    # (i.e. if the top 250 visualls all have more favs than the top
    # 250 pixels).
    #
    # In that case, switch up the conditions until the query works.
    ret = botb.entry_list(
        sort="favs",
        desc=True,
        conditions=[Condition("format_token", "IN", ["pixel", "visuall"])],
        max_items=500,
    )
    n_pixels = 0
    n_visualls = 0
    for entry in ret:
        assert entry.format_token in ("pixel", "visuall")
        if entry.format_token == "pixel":
            n_pixels += 1
        if entry.format_token == "visuall":
            n_visualls += 1
    assert n_pixels > 0
    assert n_visualls > 0

    # List playlists for entry
    ret_ids = botb.entry_get_playlist_ids(66768)
    assert ret_ids

    ret = botb.entry_get_playlists(66768)
    assert ret
    for e in ret:
        assert type(e) is pybotb.types.Playlist
        assert e.id in ret_ids

    ret = botb.entry_get_favorites(73426)
    assert ret
    for fav in ret:
        assert fav.entry_id == 73426

    ret = botb.entry_get_tags(73426)
    assert ret
    for tag in ret:
        assert tag.entry_id == 73426


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
    assert type(ret) is pybotb.types.Favorite

    # List
    ret = [
        f
        for f in botb.favorite_list(
            sort="id", desc=True, filters={"botbr_id": 16333}, max_items=50
        )
    ]
    assert ret
    for fav in ret:
        assert fav.botbr_id == 16333


def test_botb_api_group_thread(botb):
    """Test group_thread API methods."""
    # Load
    ret = botb.group_thread_load(41903)
    assert ret
    assert ret.id == 41903

    # Load 404
    ret = botb.group_thread_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.group_thread_random()
    assert ret
    assert type(ret) is pybotb.types.GroupThread

    # List
    ret = [g for g in botb.group_thread_list(sort="id", desc=True, max_items=50)]
    assert ret
    for thread in ret:
        assert type(thread) is pybotb.types.GroupThread

    # Search
    ret = botb.group_thread_search("api")
    assert ret
    for thread in ret:
        assert type(thread) is pybotb.types.GroupThread
        assert "api" in thread.title.lower()


def test_botb_api_lyceum_article(botb):
    """Test lyceum_article API methods."""
    # Load
    ret = botb.lyceum_article_load(360)
    assert ret
    assert ret.id == 360

    # Load 404
    ret = botb.lyceum_article_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.lyceum_article_random()
    assert ret
    assert type(ret) is pybotb.types.LyceumArticle

    # List
    ret = [a for a in botb.lyceum_article_list(sort="id", desc=True, max_items=50)]
    assert ret
    for article in ret:
        assert type(article) is pybotb.types.LyceumArticle

    # Search
    ret = botb.lyceum_article_search("api")
    assert ret
    for article in ret:
        assert type(article) is pybotb.types.LyceumArticle
        assert "api" in article.title.lower()


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
    assert type(ret) is pybotb.types.Palette

    # List
    ret = [
        p
        for p in botb.palette_list(
            sort="id", desc=True, filters={"color1": "e4fefe"}, max_items=50
        )
    ]
    assert ret
    for palette in ret:
        assert palette.color1 == "e4fefe"

    # Current default
    ret = botb.palette_current_default()
    assert ret
    assert type(ret) is pybotb.types.Palette


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
    assert type(ret) is pybotb.types.Playlist

    # List
    ret = [p for p in botb.playlist_list(sort="id", desc=True)]
    assert ret

    # List entries for playlist
    ret_ids = botb.playlist_get_entry_ids(115)

    ret = botb.playlist_get_entries(115)
    for e in ret:
        assert type(e) is pybotb.types.Entry
        assert e.id in ret_ids


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
    assert type(ret) is pybotb.types.Tag

    # List
    ret = [
        t
        for t in botb.tag_list(
            sort="id", desc=True, filters={"entry_id": 71306}, max_items=50
        )
    ]
    assert ret
    for tag in ret:
        assert tag.entry_id == 71306

    # Cloud by substring
    ret = botb.tag_cloud_by_substring("core")
    assert ret

    # Get entries
    ret = [e for e in botb.tag_get_entries("ambient", max_items=25)]
    assert len(ret) == 25


def test_botb_api_daily_stats(botb):
    """Test daily_stats API methods."""
    # Load
    ret = botb.daily_stats_load(100)
    assert ret
    assert ret.id == 100

    # Load 404
    ret = botb.daily_stats_load(12345678987654321)
    assert ret is None

    # Random
    ret = botb.daily_stats_random()
    assert ret
    assert type(ret) is pybotb.types.DailyStats

    # List
    ret = [d for d in botb.daily_stats_list(sort="id", desc=True, max_items=50)]
    assert ret
    for stat in ret:
        assert type(stat) is pybotb.types.DailyStats


def test_botb_api_botbr_stats(botb):
    """Test botbr_stats API methods."""
    # Load by BotBr
    ret = botb.botbr_stats_by_botbr_id(16333)
    assert ret
    for stat in ret:
        assert type(stat) is pybotb.types.BotBrStats

    ret = botb.botbr_stats_days_back(16333, 5)
    assert ret
    for stat in ret:
        assert type(stat) is pybotb.types.BotBrStats

    # Random
    ret = botb.botbr_stats_random()
    assert ret
    assert type(ret) is pybotb.types.BotBrStats


def test_botb_api_misc(botb):
    """Test miscelaneous API methods."""
    # Firki interpret
    assert botb.firki_interpret("firki '[b]test'[/b]") == "firki <b>test</b>"

    # Spriteshit version
    assert type(botb.spriteshit_version()) is str
