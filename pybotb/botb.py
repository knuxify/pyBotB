# SPDX-License-Identifier: MIT
"""Code for interfacing with BotB."""

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
import pytz
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Tuple,
    Optional,
    Union,
    Self,
)
from urllib.parse import quote, urlencode
import re

try:  # Python >= 3.11
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum  # type: ignore

from . import VERSION
from .utils import Session, unroll_payload, cached_property_dep, param_stringify

#: Level-up point requirements for a BotBr.
#:
#: Fetched from https://battleofthebits.com/api/v1/botbr/levels/.
#: TODO: Fetch this at runtime.
LEVELS = [
    0,
    9,
    16,
    28,
    48,
    84,
    148,
    259,
    452,
    791,
    1265,
    1897,
    2657,
    3453,
    4316,
    5396,
    6475,
    7652,
    8947,
    10241,
    11652,
    13771,
    16831,
    21774,
    28615,
    36487,
    45571,
    56024,
    72310,
    92620,
    118328,
    245767,
    510459,
    1060222,
    99999999,
]


class BadgeLevel(IntEnum):
    """Enum for BotBr badge_levels values."""

    #: No badge unlocked (< 7 progress points; not actually used on-site.)
    NOT_UNLOCKED = 0
    #: Regular badge unlocked (7 progress points).
    REGULAR = 1
    #: Bronze badge unlocked (28 progress points).
    BRONZE = 2
    #: Silver badge unlocked (56 progress points).
    SILVER = 3
    #: Gold badge unlocked (100 progress points).
    GOLD = 4


@dataclass
class BotBr:
    """
    Represents a BotBr.

    Properties directly match API data, except where noted otherwise.
    """

    #: String representing the aura PNG name for this BotBr; usually the BotBr ID zero-
    #: padded to 8 characters.
    #:
    #: This is used to calculate the aura URL in :attr:`.BotBr.aura_url`.
    aura: str

    #: Fallback color for the aura, as a hex value (#ffffff).
    aura_color: str

    @property
    def aura_url(self) -> str:
        """
        URL to the aura PNG; calculated from :attr:`.BotBr.aura`.

        This is a pyBotB-specific property.
        """
        return f"https://battleofthebits.com/disk/botbr_auras/{self.aura}.png"

    #: URL to the BotBr's current avatar.
    avatar_url: str

    #: Dictionary where the key is the format name and the value is the badge level
    #: (i.e. regular, bronze, silver, gold); see :py:enum:`pybotb.botb.BadgeLevel`
    #: for possible values.
    #:
    #: This lists *unlocked badges*, and is not to be confused with *badge progress*
    #: (badge progress points are what unlocks badges). Badge progress is not exposed
    #: through the official API and can only be fetched through the TODO hack method.
    badge_levels: Dict[str, BadgeLevel]

    #: Amount of boons that the BotBr currently has.
    boons: float

    #: The BotBr's class; i.e., the class that appears next to the level on-site.
    #: This class is derived from the highest points in the points array at level-up
    #: time.
    #:
    #: In the BotB API, this field is named "class"; however, it is renamed here to
    #: avoid collisions with the class keyword used by Python.
    botbr_class: str

    #: String containing HTML div representing the icon. This is BotB-specific and
    #: likely of not much use to implementations.
    class_icon: str

    #: String representing the creation date of the BotBr's account, in YYYY-MM-DD
    #: format, in the US East Coast timezone (same as all other dates on-site).
    #:
    #: The creation date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.create_date`.
    create_date_str: str

    @cached_property_dep("create_date_str")
    def create_date(self) -> datetime:
        """
        Account creation date as a datetime object.

        For the raw string, see
        :attr:`.BotBr.create_date_str`.
        """
        return datetime.strptime(self.create_date_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: The BotBr's ID.
    id: int

    #: String representing the date on which the BotBr was last seen on the site, in
    #: YYYY-MM-DD format, in the US East Coast timezone (same as all other dates on-
    #: site).
    #:
    #: The last-on date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.laston_date`.
    laston_date_str: str

    @cached_property_dep("laston_date_str")
    def laston_date(self) -> datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see
        :attr:`.BotBr.laston_date_str`.
        """
        return datetime.strptime(self.laston_date_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: The BotBr's current level.
    level: int

    #: The BotBr's username.
    name: str

    #: The ID of the palette used by the BotBr.
    palette_id: int

    #: The total amount of points amassed by the BotBr. (This number is always >= 0).
    points: int

    #: Dictionary with class name as the key and the amount of points as the value.
    #: See https://battleofthebits.com/lyceum/View/BotBr%20Classes for an overview
    #: of classes.
    #:
    #: Notes:
    #:
    #: * Some old BotBrs might have lowercase class points - these are counted
    #:   separately.
    #: * There is also a bugged out empty point class, which is also counted
    #:   separately (see https://battleofthebits.com/barracks/Profile/atropine/) -
    #:   this might break if you do a boolean comparison against the class name!
    #: * Individual point counts may be negative numbers (e.g. latist points
    #:   which are always below 0, but also e.g. -5 class points for having
    #:   an entry with no votes) - however, these do not sum up into the score in
    #:   the points variable.
    points_array: Dict[str, int]

    #: The URL to the BotBr's profile.
    profile_url: str

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a BotBr object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting BotBr object.
        """
        payload_parsed = payload.copy()

        # SITE BUG: empty points_array becomes a list instead of a dict
        if isinstance(payload_parsed["points_array"], list):
            payload_parsed["points_array"] = {}
        else:
            for key, val in payload_parsed["points_array"].copy().items():
                payload_parsed["points_array"][key] = int(val)

        ret = unroll_payload(
            cls,
            payload_parsed,
            payload_to_attr={
                "class": "botbr_class",
                "create_date": "create_date_str",
                "laston_date": "laston_date_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<BotBr: {self.name} (Level {self.level} {self.botbr_class}, ID {self.id})>"

    def __str__(self):
        return self.__repr__()


class Medium(StrEnum):
    """
    Enum for different medium types; not to be confused with formats.

    The numerical values are pyBotB-specific; on the Entry, object, this value is
    derived from "medium_audio", "medium_visual", etc. properties of the API.
    """

    OTHER = "other"
    AUDIO = "audio"
    VISUAL = "visual"


@dataclass
class Format:
    """Represents a format."""

    #: Short description of the format.
    description: str

    #: The HTML representation of the icon, likely not of use to implementations.
    icon: str

    #: The direct URL to the icon for this format (with https://battleofthebits.com prefix).
    icon_url: str

    #: ID of the format.
    id: int

    #: Medium the format belongs to.
    medium: Medium

    #: Maximum file size in bytes.
    maxfilesize: int

    #: Maximum file size in a human-readable format,
    maxfilesize_human: str

    #: Which class this format gives points of.
    point_class: str

    #: Title of the format.
    title: str

    #: Token of the format.
    #:
    #: This is a short, lowercase identifier used in lieu of the identifier
    #: in many APIs.
    token: str

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict):
        """
        Convert a JSON payload (provided as a dict) into a BotBr object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting BotBr object.
        """
        payload_parsed = payload.copy()

        # HACK: some maxfilesize values are malformed and have stray unicode characters.
        # Extract just the number.
        if type(payload["maxfilesize"]) is str:
            payload_parsed["maxfilesize"] = int(
                "".join(re.findall(r"\d+", payload["maxfilesize"].strip()))
            )

        ret = unroll_payload(cls, payload_parsed)
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<Format: {self.title} ({self.token}) (ID {self.id})>"

    def __str__(self):
        return self.__repr__()


class BattlePeriod(StrEnum):
    """String enum containing battle period values."""

    #: Upcoming battle.
    WARMUP = "warmup"

    #: Entry period.
    ENTRY = "entry"

    #: Voting period.
    VOTE = "vote"

    #: Votes are being tallied.
    #:
    #: Not actually returned by the site due to a bug.
    TALLY = "tally"

    #: Battle has ended.
    END = "end"


@dataclass
class Battle:
    """Represents a battle."""

    #: ID of the battle.
    id: int

    #: Title of the battle.
    title: str

    #: URL to the battle.
    url: str

    #: URL to the entry list page of the battle.
    profile_url: str

    #: Full URL to the battle cover art (with https://battleofthebits.com prefix).
    cover_art_url: str

    #: ID of the BotBr hosting this battle. In the case of battles with multiple
    #: hosts (some majors do this), this is set to 1 (TODO verify?).
    botbr_id: int

    #: String containing names of battle hosts, joined with a " + " sign.
    hosts_names: str

    #: The battle's "type" attribute.
    #:
    #: The value is set to 3 for XHBs; all other values are majors. Known
    #: non-XHB type values:
    #:
    #: * 0 and 1 are used for various majors
    #: * 2 was used for some "3xTheme Battle" majors and the "48 Hour Game Jam I" major
    #: * 4 was used for the "Doom" major
    #: * 25 was used for the "BotB Advent Calendar 2020" major
    #:
    #: In any case, it is safe to assume that any type value other than 3 means it's not
    #: an XHB.
    type: int = field()

    @property
    def is_xhb(self) -> bool:
        """
        Whether or not this battle is an X Hour Battle/minor battle.

        :returns: True if the battle is an XHB, False otherwise.
        """
        return self.type == 3

    @property
    def is_major(self) -> bool:
        """
        Whether or not this battle is a major battle.

        :returns: True if the battle is a major, False otherwise.
        """
        return self.type != 3

    #: Amount of entries submitted.
    entry_count: int

    #: String representing the date and time at which the battle starts, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: The start date is also converted to a datetime for developer convenience;
    #: see :attr:`.start`.
    start_str: str

    @cached_property_dep("start_str")
    def start(self) -> datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see :attr:`.start_str`.
        """
        return datetime.strptime(self.start_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: String representing the date and time at which the battle ends, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: If :attr:`.period` is "vote", this signifies the end of the voting
    #: period.
    #:
    #: The end date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.end`.
    end_str: str = field()

    @cached_property_dep("end_str")
    def end(self) -> datetime:
        """
        Date and time at which the battle ends.

        If :attr:`.period` is "vote", this signifies the end of the voting
        period.

        For the raw string, see :attr:`.end_str`.
        """
        return datetime.strptime(self.end_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: List of format tokens for this battle. For XHBs, this will contain one
    #: item; for majors, there may be more formats.
    format_tokens: List[str]

    #: Current battle period. "warmup" for upcoming battles, "entry" for
    #: entry period, "vote" for voting period, "end" for end period.
    period: BattlePeriod

    #: String representing the date and time at which the battle ends, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: For major battles, this signifies the "final results" datetime;
    #: for the current battle period's end date, see :attr:`.period_end`.
    #:
    #: The end date is also converted to a datetime for developer convenience;
    #: see :attr:`.end`.
    period_end_str: str = field()

    @cached_property_dep("period_end_str")
    def period_end(self) -> datetime:
        """
        Date and time at which the current battle period ends.

        If :attr:`.period` is "vote", this signifies the period_end of the voting
        period.

        For the raw string, see :attr:`.period_end_str`.
        """
        return datetime.strptime(self.period_end_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: False if the "no late penalties" option is enabled.
    #:
    #: (TODO, this does not seem to actually be returned by the site)
    # disable_penalty: bool = False

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a BotBr object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting BotBr object.
        """
        payload_parsed = payload.copy()

        #: HACK: Battles in the tally period have no "period" property,
        #: but they do have a period_end.
        if "period_end" in payload_parsed and "period" not in payload_parsed:
            payload_parsed["period"] = "tally"

        ret = unroll_payload(
            cls,
            payload_parsed,
            payload_to_attr={
                "start": "start_str",
                "end": "end_str",
                "period_end": "period_end_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<Battle: {self.title} (Is XHB: {self.is_xhb}, hosted by: {self.hosts_names}, ID {self.id})>"

    def __str__(self):
        return self.__repr__()


@dataclass
class EntryAuthor:
    """
    Represents an entry author, as returned in the "authors" field of the entry
    API.
    """

    #: String representing the aura PNG name for this BotBr; usually the BotBr ID zero-
    #: padded to 8 characters.
    #:
    #: This is used to calculate the aura URL in :attr:`.aura_url`.
    aura: str

    #: Fallback color for the aura, as a hex value (#ffffff).
    aura_color: str

    @property
    def aura_url(self) -> str:
        """
        URL to the aura PNG; calculated from :attr:`.aura`.

        This is a pyBotB-specific property.
        """
        return f"https://battleofthebits.com/disk/botbr_auras/{self.aura}.png"

    #: Relative URL to the BotBr's current avatar (/disk/...)
    avatar: str

    #: Relative URL to the BotBr's avatar at the time of the entry's submission (/disk/...)
    avatar_from_time: str

    #: The BotBr's class; i.e., the class that appears next to the level on-site.
    #: This class is derived from the highest points in the points array at level-up
    #: time.
    #:
    #: In the BotB API, this field is named "class"; however, it is renamed here to
    #: avoid collisions with the class keyword used by Python.
    botbr_class: str

    #: String containing HTML div representing the icon. This is BotB-specific and
    #: likely of not much use to implementations.
    class_icon: str

    #: The country code of the author.
    country_code: str

    #: The country name of the author.
    country_name: str

    #: The author's BotBr ID.
    id: int

    #: The author's current level.
    level: int

    #: The author's username.
    name: str

    #: The full URL to the author's BotB profile.
    profile_url: str

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a BotBr object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting BotBr object.
        """
        ret = unroll_payload(
            cls,
            payload,
            payload_to_attr={
                "class": "botbr_class",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<EntryAuthor: {self.name} (Level {self.level} {self.botbr_class}, ID {self.id})>"

    def __str__(self):
        return self.__repr__()


@dataclass
class Entry:
    """Represents a battle entry."""

    #: List of authors for the entry.
    authors: List[BotBr]

    #: A string containing the names of all authors joined with a " + " symbol.
    authors_display: str

    #: ID of the BotBr who submitted this entry.
    botbr_id: int

    #: The BotBr who submitted this entry.
    botbr: BotBr

    #: ID of the battle this entry was submitted to.
    battle_id: int

    #: The battle this entry was submitted to.
    battle: Battle

    #: String representing the submission date of this entry in YYYY-MM-DD
    #: HH:MM:SS format, in the US East Coast timezone (same as all other dates
    #: on the site).
    #:
    #: The creation date is also converted to a datetime for developer convenience;
    #: see :attr:`.Entry.datetime`.
    datetime_str: str = field()

    @cached_property_dep("datetime_str")
    def datetime(self) -> datetime:
        """
        Account creation date as a datetime object.

        For the raw string, see
        :attr:`.Entry.datetime_str`.
        """
        return datetime.strptime(self.datetime_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: The submission date in a human-readable format, as displayed on BotB.
    #:
    #: Like the datetime string, this is stored in the US East Coast timezone;
    #: implementations will likely want to create their own string based on
    #: the :attr:`.Entry.datetime` property.
    datetime_display: str

    #: Amount of downloads the entry has (note the deliberate typo).
    donloads: int

    @property
    def downloads(self) -> int:
        """Longhand for "donloads", for spelling convenience."""
        return self.donloads

    @downloads.setter
    def downloads(self, downloads: int):
        self.donloads = downloads

    #: Relative URL to the entry source file, for downloading (note the deliberate typo).
    donload_url: str

    @property
    def download_url(self) -> str:
        """Longhand for "donload_url", for spelling convenience."""
        return self.donload_url

    @download_url.setter
    def download_url(self, download_url: str):
        self.donload_url = download_url

    #: Amount of favorites the entry has.
    favs: int

    #: The token of the entry's format. For a list, see TODO.
    format_token: str

    #: The entry's format.
    format: Format

    #: ???
    gov: float

    #: ID of the entry.
    id: int

    #: Whether the entry is late or not.
    late: bool

    #: Medium of the entry; see :py:enum:`.Medium` for possible values.
    #:
    #: This is consolidated from "medium_*" variables ("medium_audio", "medium_visual",
    #: etc.)
    medium: Medium

    #: Amount of plays this entry has.
    plays: int

    #: Amount of comments ("posts") under this entry.
    posts: int

    #: URL to the entry's page on the site.
    profile_url: str

    #: ???
    q: int

    #: The entry's title.
    title: str

    #: Relative URL to the entry thumbnail; empty for entries without a
    #: thumbnail (i.e. non-visual entries).
    thumbnail_url: str

    #: Amount of votes this entry got.
    votes: int

    #: URL to the player for the entry.
    view_url: str

    #: Preview URL.
    preview_url: str

    #: Length of the entry, in seconds.
    #:
    #: Only present for audio entries.
    length: float = 0

    #: Relative player URL for the entry ("/player/Entry/{id}" format).
    #:
    #: Present for audio and visual entries, except for some non-audio entries
    #: with archives or other filetypes. Also not present for non-rendered entries.
    listen_url: Optional[str] = None

    #: Direct URL to the source file of an audio entry.
    #:
    #: None for non-audio entries. (The API returns False for non-audio entries;
    #: we turn it to None for API convenience.)
    play_url: Optional[str] = None

    #: YouTube URL for this entry, if any.
    youtube_url: Optional[str] = None

    #: Rank of the entry.
    #:
    #: Only present once the battle is over; returns None otherwise.
    rank: Optional[int] = None

    #: English plural suffix for the rank (e.g "st" for 1st, "nd" for 2nd, etc.)
    #:
    #: If the battle is not over yet, this is an empty string.
    rank_suffix: str = ""

    #: HTML representation of rank; likely not of use to implementations.
    #:
    #: If the battle is not over yet, this is "?/{entry count}".
    rank_display: str = ""

    #: Score of the entry.
    #:
    #: Only present once the battle is over; returns None otherwise.
    score: Optional[float] = None

    #: HTML representation of score; likely not of use to implementations.
    #:
    #: If the battle is not over yet, this is an empty string.
    score_display: str = ""

    #: HTML representation of trophies this entry has.
    #:
    #: If the battle is not over yet, this is None.
    #: TODO: make a custom prop out of this
    trophy_display: Optional[str] = None

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into an Entry object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Entry object.
        """
        payload_parsed = payload.copy()

        if "medium_audio" in payload_parsed:
            payload_parsed["medium"] = Medium.AUDIO
        elif "medium_visual" in payload_parsed:
            payload_parsed["medium"] = Medium.VISUAL
        else:
            payload_parsed["medium"] = Medium.OTHER

        # HACK: some old entries from 2009 don't have an attached comment thread,
        # which causes the "posts" value to be missing
        # (e.g. all entries in https://battleofthebits.com/arena/Battle/335).
        # Add "posts" = 0 manually if that happens.
        if "posts" not in payload_parsed:
            payload_parsed["posts"] = 0

        ret = unroll_payload(
            cls,
            payload_parsed,
            payload_to_attr={
                "datetime": "datetime_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f'<Entry: "{self.title}" by {self.authors_display} (Format {self.format_token}, Battle {self.battle.name}, ID {self.id})>'

    def __str__(self):
        return self.__repr__()


@dataclass
class Favorite:
    """A favorite on an entry."""

    #: ID of the favorite.
    id: int

    #: ID of the BotBr who favorited.
    botbr_id: int

    #: ID of the favorited entry.
    entry_id: int

    #: ???
    much: int

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(cls, payload)
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<Favorite on entry {self.entry_id} by BotBr {self.botbr_id} (ID {self.id})>"

    def __str__(self):
        return self.__repr__()


class GroupID(IntEnum):
    """Forum group IDs."""

    #: "Bulletins" group.
    BULLETINS = 1

    #: "News" group.
    NEWS = 2

    #: ??? ("elders only, n00b" when trying to access)
    INTERNAL = 3

    #: "Entries" group (entry comments).
    ENTRIES = 4

    #: "Battles" group (battle comments).
    BATTLES = 5

    #: "Photos" group.
    PHOTOS = 6

    #: "BotB update log" group.
    #:
    #: Redirects to https://battleofthebits.com/academy/Updates/ on-site;
    #: appears to be unused (conains one post with ID 804 which also redirects
    #: there).
    UPDATE_LOG = 7

    #: "n00b s0z" group.
    N00B_S0Z = 8

    #: "mail" group.
    MAIL = 9

    #: "Bug Reports and Feature Requests" group.
    BUG_REPORTS_AND_FEATURE_REQUESTS = 10

    #: "Smeesh" group.
    SMEESH = 11

    #: "Project Dev" group.
    PROJECT_DEV = 12

    #: "BotBrs" group (BotBr profile comments).
    BOTBRS = 13

    #: "Lyceum" group (discussions for lyceum entries).
    LYCEUM = 14


@dataclass
class GroupThread:
    """
    A group thread - i.e. a thread in a forum group, containing posts.

    Forum threads and BotBr/entry/battle comment threads are all group threads.
    """

    #: ID of the group thread.
    id: int

    #: ID of the forum group this thread belongs to; see `:enum:.GroupID` for
    #: possible values.
    group_id: GroupID

    #: Title of the thread.
    title: str

    #: Timestamp of the first post in the thread, in YYYY-MM-DD HH:MM:SS format,
    #: in the US East Coast timezone (same as all other dates on the site).
    first_post_timestamp_str: str

    @cached_property_dep("first_post_timestamp_str")
    def first_post_timestamp(self) -> datetime:
        """
        First post's timestamp as a datetime object.

        For the raw string, see :attr:`.first_post_timestamp_str`.
        """
        return datetime.strptime(
            self.first_post_timestamp_str, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=pytz.timezone("America/Los_Angeles"))

    #: Timestamp of the last post in the thread, in YYYY-MM-DD HH:MM:SS format,
    #: in the US East Coast timezone (same as all other dates on the site).
    #:
    #: None if the thread only contains one post.
    last_post_timestamp_str: Optional[str] = None

    @cached_property_dep("last_post_timestamp_str")
    def last_post_timestamp(self) -> Optional[datetime]:
        """
        Last post's timestamp as a datetime object.

        None if the thread only contains one post.

        For the raw string, see :attr:`.last_post_timestamp_str`.
        """
        if self.last_post_timestamp_str is None:
            return None

        return datetime.strptime(
            self.last_post_timestamp_str, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=pytz.timezone("America/Los_Angeles"))

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(
            cls,
            payload,
            payload_to_attr={
                "first_post_timestamp": "first_post_timestamp_str",
                "last_post_timestamp": "last_post_timestamp_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<GroupThread: {self.title} (ID {self.id})>"

    def __str__(self):
        return self.__repr__()


@dataclass
class LyceumArticle:
    """Represents an article on the Lyceum."""

    #: ID of the article.
    id: int

    #: Title of the article.
    title: str

    #: URL of the article.
    profile_url: str

    @property
    def url(self) -> str:
        """Shorthand for `:attr:.profile_url`."""
        return self.profile_url

    @url.setter
    def url(self, url: str):
        self.profile_url = url

    #: The raw text of the article in Firki markup.
    text_firki: str

    #: The raw text of the article, stripped of Firki markup.
    text_stripped: str

    #: Amount of views this article has.
    views: int

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a PlaylistToEntry object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(cls, payload)

        return ret

    def __repr__(self):
        return f"<LyceumArticle: {self.title} (ID: {self.id})>"

    def __str__(self):
        return self.__repr__()


@dataclass
class Tag:
    """A tag on an entry."""

    #: ID of the tag.
    id: int

    #: ID of the entry this tag applies to.
    entry_id: int

    #: The tag applied to the entry.
    tag: str

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(cls, payload)
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f'<Tag "{self.tag}" on entry {self.entry_id} (ID {self.id})>'

    def __str__(self):
        return self.__repr__()


@dataclass
class Palette:
    """Color palette."""

    #: ID of the palette.
    id: int

    #: Title of the palette.
    title: str

    @property
    def css_url(self):
        """
        URL to the palette CSS.

        This is a CSS file hosted on battleofthebits.com which contains a :root
        directive with the colors as CSS variables. Each color has its hex code stored
        in the --colorX variable, with the individual RGB components stored in
        --colorX_r, --colorX_g and --colorX_b for red, green and blue respectively.

        This variable is derived from the ID.
        """
        return f"https://battleofthebits.com/disk/palette_vars/{self.id}"

    #: ID of the BotBr who made the palette.
    botbr_id: int

    #: Color 1 (text), in hex format without "#" prefix.
    color1: str

    #: Color 2 (link), in hex format without "#" prefix.
    color2: str

    #: Color 3 (button), in hex format without "#" prefix.
    color3: str

    #: Color 4 (box), in hex format without "#" prefix.
    color4: str

    #: Color 5 (bottom), in hex format without "#" prefix.
    color5: str

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(cls, payload)
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f'<Palette "{self.title}" by BotBr {self.botbr_id} (ID {self.id})>'

    def __str__(self):
        return self.__repr__()


@dataclass
class Playlist:
    """A playlist containing entries."""

    #: ID of the playlist.
    id: int

    #: ID of the BotBr who made the playlist.
    botbr_id: int

    #: Title of the playlist
    title: str

    #: Amount of entries in the playlist.
    count: int

    #: Total runtime (sum of lengths) of entries with lengths in this playlist,
    #: in seconds.
    runtime: int

    #: String representing the date on which the BotBr was last seen on the site, in
    #: YYYY-MM-DD format, in the US East Coast timezone (same as all other dates on-
    #: site).
    #:
    #: The last-on date is also converted to a datetime for developer convenience;
    #: see :attr:`.date_create`.
    date_create_str: str

    @cached_property_dep("date_create_str")
    def date_create(self) -> datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see
        :attr:`.date_create_str`.
        """
        return datetime.strptime(self.date_create_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: String representing the date on which the BotBr was last seen on the site, in
    #: YYYY-MM-DD format, in the US East Coast timezone (same as all other dates on-
    #: site).
    #:
    #: The last-on date is also converted to a datetime for developer convenience;
    #: see :attr:`.date_modify`.
    date_modify_str: str = field()

    @cached_property_dep("date_modify_str")
    def date_modify(self) -> datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see
        :attr:`.date_modify_str`.
        """
        return datetime.strptime(self.date_modify_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: Description of the playlist.
    description: Optional[str] = None

    #: ID of the entry used as the thumbnail, or None if none is set.
    #:
    #: To get the Entry object for the thumbnail, use
    #:   BotBr.entry_load(playlist.thumbnail_id).
    #:
    #: To get the URL of the thumbnail, get the `:prop:.Entry.thumbnail_property`
    #: property of the entry object fetched with the function above.
    thumbnail_id: Optional[int] = None

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(
            cls,
            payload,
            payload_to_attr={
                "date_create": "date_create_str",
                "date_modify": "date_modify_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f'<Playlist "{self.title}" by BotBr {self.botbr_id} ({self.count} items, ID {self.id})>'

    def __str__(self):
        return self.__repr__()


@dataclass
class PlaylistToEntry:
    """Link between playlist and entry returned by the playlist_to_entry API."""

    #: ID of the playlist
    playlist_id: int

    #: ID of the entry
    entry_id: int

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a PlaylistToEntry object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(cls, payload)

        return ret

    def __repr__(self):
        return (
            f"<PlaylistToEntry: playlist {self.playlist_id} <-> entry {self.entry_id}>"
        )

    def __str__(self):
        return self.__repr__()


@dataclass
class DailyStats:
    """
    A single entry in the BotB daily site stats table.

    Note that statistics apply to the given date in the US East Coast timezone; if you
    want to get statistics for a date in your timezone, you will have to aggregate data
    from multiple days.
    """

    #: ID of the daily stats table entry.
    id: int

    #: String representing the date of the statistic, in YYYY-MM-DD format,
    #: in the US East Coast timezone (same as all other dates on-site).
    #:
    #: This date is also converted to a datetime for developer convenience;
    #: see :attr:`.date`.
    date_str: str

    @cached_property_dep("date_str")
    def date(self) -> datetime:
        """
        Statistic date as a datetime object.

        For the raw string, see
        :attr:`.date_str`.
        """
        return datetime.strptime(self.date_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: Total amount of page views.
    page_views: int

    #: Total amount of entry plays.
    plays: int

    #: Total amount of entry downloads (note the deliberate typo).
    donloads: int

    @property
    def downloads(self) -> int:
        """Longhand for "donloads", for spelling convenience."""
        return self.donloads

    @downloads.setter
    def downloads(self, downloads: int):
        self.donloads = downloads

    #: Amount of unique IPs visiting the site.
    ip_count: int

    #: Amount of entries submitted to the site.
    entry_count: int

    #: Amount of BotBrs seen on the site.
    botbr_count: int

    #: Amount of users seen on the site; same as :attr:`.botbr_count`.
    user_count: int

    #: Amount of group thread posts made on the site.
    post_count: int

    #: Total amount of boons owned by BotBrs, including the bank value,
    #: rounded to an integer.
    economic_pool: int

    #: Average amount of boons owned by BotBrs, rounded to an integer.
    avg_debit: int

    #: Current amount of boons held by the BotB Bank (BotB account), rounded
    #: to an integer.
    bank_debit: int

    #: How much boons the bank has given out to BotBrs.
    bank_credit: int

    #: Total points of all BotBrs on the site.
    total_points: int

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(
            cls,
            payload,
            payload_to_attr={
                "date": "date_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<BotBrStats: {self.label} = {self.val} for BotBr {self.botbr_id} on {self.date_str}>"

    def __str__(self):
        return self.__repr__()


@dataclass
class BotBrStats:
    """
    A single entry in the BotBr stats table.

    Note that statistics apply to the given date in the US East Coast timezone; if you
    want to get statistics for a date in your timezone, you will have to aggregate data
    from multiple days.
    """

    #: ID of the BotBr the statistic applies to.
    botbr_id: int

    #: Label of the statistic.
    #:
    #: "level" for level, "boons" for boon count, "a_light" for aura light
    #: points, "a_ack" for aura ack points, "a_dark" for aura dark points,
    #: class name for class point amount.
    label: str

    #: Value of the statistic.
    val: float

    #: String representing the date of the statistic, in YYYY-MM-DD format,
    #: in the US East Coast timezone (same as all other dates on-site).
    #:
    #: This date is also converted to a datetime for developer convenience;
    #: see :attr:`.date`.
    date_str: str

    @cached_property_dep("date_str")
    def date(self) -> datetime:
        """
        Statistic date as a datetime object.

        For the raw string, see
        :attr:`.date_str`.
        """
        return datetime.strptime(self.date_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: Raw JSON payload used to create this class. Useful if e.g. you need a raw
    #: value that isn't exposed through the class.
    _raw_payload: Optional[dict] = field(default=None, repr=False)

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Favorite object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Favorite object.
        """
        ret = unroll_payload(
            cls,
            payload,
            payload_to_attr={
                "date": "date_str",
            },
        )
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<BotBrStats: {self.label} = {self.val} for BotBr {self.botbr_id} on {self.date_str}>"

    def __str__(self):
        return self.__repr__()


@dataclass(slots=True)
class Condition:
    """Represents a condition passed to a "list" API query."""

    #: Property that the condition applies to.
    property: str

    #: Operator for the condition.
    operator: str

    #: Operand for the condition.
    operand: Union[int, str, bool, List[Any], Tuple[Any]]

    def to_dict(self) -> dict:
        """
        Return the condition as a dictionary that can be passed to the list API.

        :returns: The condition represented as a dictionary.
        """
        return dataclasses.asdict(self)


class PaginatedList:
    """
    Iterable implementation for paginated API requests.

    Automatically handles progressing to the next page, etc. Fetches as many objects as
    possible (500 per page), unless max_items is set to a lower value.
    """

    def __init__(self, func: Callable, max_items: int = 0, *args, **kwargs):
        """
        Initialize a paginated iterator.

        :param func: List function to call; must take page_number and page_length
            values.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param args: Arguments to pass to the list function.
        :param kwargs: Keyword arguments to pass to the list function.
        """
        self.func = func
        self.max_items = max_items
        self.args = args
        self.kwargs = kwargs
        if "page_number" in kwargs or "page_length" in kwargs:
            raise ValueError(
                "Paginated iterator does not accept page number or page length args"
            )

    def __iter__(self):
        count = 0  # Count is the amount of items parsed;
        index = 0  # Index is the index of the current entry on the current page;
        page = 0  # Page is the page number.

        # If we have a max_items value and it's smaller than 500, then
        # only fetch 1 page with the desired size.
        if self.max_items > 0:
            page_length = min(self.max_items, 500)
        else:
            page_length = 500

        ret = self.func(
            *self.args, **self.kwargs, page_number=page, page_length=page_length
        )
        while (self.max_items == 0 or (count < self.max_items)) and len(ret) > 0:
            if index >= len(ret):
                # If the length of the returned page is less than the max page length,
                # we've reached the end of the list; no further queries are needed
                if len(ret) < page_length:
                    return None

                # If max_items is set and larger than the max page length, make sure
                # that if we're on the last page we only fetch as many objects as we need
                if self.max_items > 500:
                    page_length = min((self.max_items - count), 500)

                # Load the next page and reset the index
                page += 1
                ret = self.func(
                    *self.args, **self.kwargs, page_number=page, page_length=page_length
                )
                index = 0

            yield ret[index]
            count += 1
            index += 1


class BotB:
    """
    BotB API class. Exposes access to the official BotB API, documented on the
    Lyceum (https://battleofthebits.com/lyceum/View/BotB+API+v1).

    This class only exposes official API endpoints. pyBotB also provides "hack"
    methods, i.e. methods based on parsed data from the site's frontend, to
    make some data available that the API does not typically expose; for those
    methods, see :py:class:`pybotb.botb.BotBHacks` (note that they may break
    at any moment).
    """

    def __init__(self, app_name=str):
        """
        Initialize the BotB API access object.

        :param app_name: App name to be used in the user agent for requests; see
            `:attr:.app_name`.
        """
        #: Internal Session object.
        self._s = Session()

    @property
    def app_name(self) -> str:
        """
        Custom app name; added to the user agent.

        Setting this is highly recommended.
        """
        try:
            return self._app_name
        except AttributeError:
            return ""

    @app_name.setter
    def app_name(self, app_name: str):
        self._app_name = app_name
        self._s.set_user_agent(f"{app_name} (pyBotB {VERSION})")

    # Common API methods

    def _load(self, object_type: str, object_id: int) -> Union[dict, None]:
        """
        Load information about an object with the given type and ID.

        This function is primarily used internally; for API users, use one of the
        load_{object_type}_* functions instead.

        :param object_type: Object type string.
        :param object_id: ID of the object.
        :returns: A dictionary containing the JSON result, or None if not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/{object_type}/load/{object_id}",
            handle_notfound=True,
        )
        if ret.status_code == 404:
            return None
        elif ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            return ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

    def _list(
        self,
        object_type: str,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[dict]:
        """
        Perform a listing query for the provided object type with the given
        filtering/sorting/pagination options.

        This function is primarily used internally; for API users, use one of the
        load_{object_type}_* functions instead.

        :param object_type: Object type string.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 500).
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead. If both conditions and filters are passed, the filters will be
            converted to conditions and prepended to the conditions list.
        :param conditions: List of Condition objects containing list conditions.
        :returns: A list of dictionaries representing the found objects.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        if desc is True and sort is None:
            raise ValueError("desc option requires sort key to be set")

        if page_length > 500:
            raise ValueError("Maximum page length is 500")

        url = f"https://battleofthebits.com/api/v1/{object_type}/list/{page_number}/{page_length}"
        params = {}

        if conditions:
            i = 0

            # Filters are ignored when passing conditions, make sure we manually
            # convert them to conditions.
            if filters:
                for fkey, fval in filters.items():
                    params[f"conditions[{i}][key]"] = fkey
                    params[f"conditions[{i}][property]"] = fkey

                    if type(fval) is int or type(fval) is str and fval.isnumeric():
                        params[f"conditions[{i}][operator]"] = "="
                        params[f"conditions[{i}][operand]"] = str(fval)
                    else:
                        params[f"conditions[{i}][operator]"] = "LIKE"
                        params[f"conditions[{i}][operand]"] = param_stringify(fval)

                    i += 1

            for cond in conditions:
                params[f"conditions[{i}][key]"] = cond.property
                params[f"conditions[{i}][property]"] = cond.property
                params[f"conditions[{i}][operator]"] = cond.operator

                if type(cond.operand) in (list, tuple):
                    # Type ignore is necessary here since mypy can't tell we check for
                    # lists/tuples only here
                    if len(cond.operand) == 0:  # type: ignore
                        raise ValueError("Length of list operand must be more than 0")
                    elif len(cond.operand) == 1:  # type: ignore
                        params[f"conditions[{i}][operand][]"] = param_stringify(
                            cond.operand[0]  # type: ignore
                        )
                    else:
                        for n in range(len(cond.operand)):  # type: ignore
                            params[f"conditions[{i}][operand][{n}]"] = param_stringify(
                                cond.operand[n]  # type: ignore
                            )

                else:
                    params[f"conditions[{i}][operand]"] = param_stringify(cond.operand)  # type: ignore

                i += 1

        if desc:
            params["desc"] = str(desc).lower()
        if sort:
            params["sort"] = sort

        if filters and not conditions:
            filter_str = ""
            for fkey, fval in filters.items():
                filter_str += f"^{fkey}~{fval}"
            filter_str = filter_str[1:]
            params["filters"] = filter_str

        if conditions:
            # Encode the parameters into form data.
            # (The "k: (None, v)" syntax is Requests-specific; it tells it to
            # encode the value as a data string, not as a file to upload.)
            params_form = dict([(k, (None, v)) for k, v in params.items()])
            ret = self._s.post(url, data=params_form)
        else:
            if params:
                url += "?" + urlencode(params)
            ret = self._s.get(url)

        if ret.status_code == 400 and "Please RTFM" in ret.text:
            raise ValueError(ret.text.split("\n")[0].split("<br>")[0])

        if not ret.text:
            return []

        try:
            return ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

    def _random(self, object_type: str) -> dict:
        """
        Get random item of the given object type.

        This function is primarily used internally; for API users, use one of the
        get_{object_type}_* functions instead.

        :param object_type: Object type string.
        :returns: A dictionary containing the JSON result.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(f"https://battleofthebits.com/api/v1/{object_type}/random")
        if ret.status_code == 404:
            raise ConnectionError(ret.text)

        try:
            return ret.json()[0]
        except Exception as e:
            raise ConnectionError(ret.text) from e

    def _search(
        self, object_type: str, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[dict]:
        """
        Search for objects with the given object type using the provided query.

        The query is checked against the title/name of the object; if an object matches,
        it is included in the results.

        :param object_type: Object type string.
        :param query: String to query for.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 500).
        :returns: A list of dictionaries containing the JSON results.
        :raises ConnectionError: On connection error.
        """
        if page_length > 500:
            raise ValueError("Maximum page length is 500")

        query_enc = quote(query, safe="")

        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/{object_type}/search/{query_enc}/{page_number}/{page_length}"
        )
        if ret.status_code == 404:
            raise ConnectionError(ret.text)

        try:
            return ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

    #
    # BotBrs
    #

    def botbr_load(self, botbr_id: int) -> Union[BotBr, None]:
        """
        Load a BotBr's info by their ID.

        :api: /api/v1/botbr/load
        :param botbr_id: ID of the botbr to load.
        :returns: BotBr object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("botbr", botbr_id)
        if ret is None:
            return None

        return BotBr.from_payload(ret)

    def _botbr_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[BotBr]:
        """
        Search for BotBrs that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.BotBr`.

        :api: /api/v1/botbr/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of BotBr objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "botbr",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(BotBr.from_payload(payload))

        return out

    def botbr_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[BotBr]:
        """
        Search for BotBrs that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.BotBr`.

        :api: /api/v1/botbr/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of BotBr objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._botbr_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def botbr_random(self) -> BotBr:
        """
        Get a random BotBr.

        :api: /api/v1/botbr/random
        :returns: BotBr object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("botbr")

        return BotBr.from_payload(ret)

    def _botbr_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[BotBr]:
        """
        Search for BotBrs that match the given query.

        :api: /api/v1/botbr/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of BotBr objects representing the search results. If the
            search returned no results, the resulting iterable will return no results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "botbr", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(BotBr.from_payload(payload))

        return out

    def botbr_search(self, query: str, max_items: int = 0) -> Iterable[BotBr]:
        """
        Search for BotBrs that match the given query.

        :api: /api/v1/botbr/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of BotBr objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._botbr_search_noiter, query=query, max_items=max_items
        )

    def botbr_get_id_for_username(self, username: str) -> Union[int, None]:
        """
        Get the ID of a BotBr by their username.

        :param username: Username of the BotBr to find the ID of.
        :returns: int containing the ID, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        for user in self.botbr_list(filters={"name": username}):
            if user.name == username:
                return user.id

        return None

    def botbr_load_for_username(self, username: str) -> Union[BotBr, None]:
        """
        Load BotBr info by username.

        :param username: Username of the BotBr to fetch the information of.
        :returns: BotBr object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        for user in self.botbr_list(filters={"name": username}):
            if user.name == username:
                return user

        return None

    def botbr_get_favorite_entries(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Entry]:
        """
        List all entries favorited by the BotBr with the given ID.

        :api: /api/v1/entry/botbr_favorites_playlist
        :param botbr_id: ID of the BotBr to get favorites for.
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Favorite objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/entry/botbr_favorites_playlist/{botbr_id}"
        )

        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            entries = ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

        out = []
        for entry in entries:
            out.append(Entry.from_payload(entry))
        return out

    def botbr_get_palettes(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> PaginatedList:
        """
        List all palettes created by the BotBr with the given ID.

        Convinience shorthand for `:py:method:.BotB.palette_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param botbr_id: ID of the BotBr to get palettes for.
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :returns: List of Palette objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"botbr_id": botbr_id}
        if filters is not None:
            _filters = filters | _filters

        return self.palette_list(
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
            max_items=max_items,
        )

    #
    # Battles
    #

    def battle_load(self, battle_id: int) -> Union[Battle, None]:
        """
        Load a battle's info by its ID.

        :api: /api/v1/battle/load
        :param battle_id: ID of the battle to load.
        :returns: Battle object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        # HACK: Battles loaded through the load endpoint don't have the period value;
        # use list instead with a filter on the ID value, and fall back to load if
        # that doesn't work.

        ret = self._list("battle", filters={"id": battle_id})
        for b in ret:
            try:
                b_id = int(b.get("id", None))
            except ValueError:
                continue
            if b_id == battle_id:
                return Battle.from_payload(b)

        ret_load = self._load("battle", battle_id)
        if ret_load is None:
            return None

        ret_load["period"] = "unknown"
        ret_load["period_end"] = ret_load.get("end", "0000-00-00 00:00:01")

        return Battle.from_payload(ret_load)

    def _battle_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Battle]:
        """
        Search for battles that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Battle`.

        :api: /api/v1/battle/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Battle objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "battle",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Battle.from_payload(payload))

        return out

    def battle_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Battle]:
        """
        Search for battles that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Battle`.

        :api: /api/v1/battle/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Battle objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._battle_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def battle_random(self) -> Battle:
        """
        Get a random battle.

        :api: /api/v1/battle/random
        :returns: Battle object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("battle")

        return Battle.from_payload(ret)

    def _battle_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[Battle]:
        """
        Search for battles that match the given query.

        :api: /api/v1/battle/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of Battle objects representing the search results. If
            the search returned no results, the resulting iterable will return no
            results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "battle", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Battle.from_payload(payload))

        return out

    def battle_search(self, query: str, max_items: int = 0) -> Iterable[Battle]:
        """
        Search for battles that match the given query.

        :api: /api/v1/battle/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of Battle objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._battle_search_noiter, query=query, max_items=max_items
        )

    def battle_current(self) -> List[Battle]:
        """
        Get a list of upcoming and ongoing battles.

        :api: /api/v1/battle/current
        :returns: List of Battle objects representing the battles. If there are no
            upcoming/ongoing battles, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get("https://battleofthebits.com/api/v1/battle/current")
        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            battles = ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

        out = []
        for b in battles:
            out.append(Battle.from_payload(b))
        return out

    #
    # Entries
    #

    def entry_load(self, entry_id: int) -> Union[Entry, None]:
        """
        Load a entry's info by their ID.

        :api: /api/v1/entry/load
        :param entry_id: ID of the entry to load.
        :returns: Entry object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("entry", entry_id)
        if ret is None:
            return None

        return Entry.from_payload(ret)

    def _entry_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Entry]:
        """
        Search for entries that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Entry`.

        :api: /api/v1/entry/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Entry objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "entry",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Entry.from_payload(payload))

        return out

    def entry_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Entry]:
        """
        Search for entries that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Entry`.

        :api: /api/v1/entry/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Entry objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._entry_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def entry_random(self) -> Entry:
        """
        Get a random entry.

        :api: /api/v1/entry/random
        :returns: Entry object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("entry")

        return Entry.from_payload(ret)

    def _entry_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[Entry]:
        """
        Search for entries that match the given query.

        :api: /api/v1/entry/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of Entry objects representing the search results. If the
            search returned no results, the resulting iterable will return no results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "entry", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Entry.from_payload(payload))

        return out

    def entry_search(self, query: str, max_items: int = 0) -> Iterable[Entry]:
        """
        Search for entries that match the given query.

        :api: /api/v1/entry/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of Entry objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._entry_search_noiter, query=query, max_items=max_items
        )

    def entry_get_tags(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Tag]:
        """
        List all tags given to entry with the given ID.

        Convinience shorthand for `:py:method:.BotB.tag_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param entry_id: ID of the entry to get tags for.
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :returns: List of Tag objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"entry_id": entry_id}
        if filters is not None:
            _filters = filters | _filters

        return self.tag_list(
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
            max_items=max_items,
        )

    def entry_get_playlist_ids(self, entry_id: int, max_items: int = 0) -> List[int]:
        """
        Get a list containing the playlist IDs of playlists that this entry has been
        added to.

        To get a list of Playlist objects, see `:method:.BotBr.entry_get_playlists`.

        :param entry_id: ID of the entry to load the playlists of.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :returns: List of playlist IDs.
        :raises ConnectionError: On connection error.
        """
        ret = PaginatedList(
            self.playlist_to_entry_list,
            filters={"entry_id": entry_id},
            max_items=max_items,
        )
        if not ret:
            return []

        return [p.playlist_id for p in ret]

    def entry_get_playlists(
        self, entry_id: int, max_items: int = 0
    ) -> Iterable[Playlist]:
        """
        Get a list of playlists that this entry has been added to.

        :param entry_id: ID of the playlist to load the entries of.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :returns: List of Playlist objects.
        :raises ConnectionError: On connection error.
        """
        playlist_ids = self.entry_get_playlist_ids(entry_id, max_items=max_items)

        condition = Condition("id", "IN", playlist_ids)

        return self.playlist_list(
            sort="id", conditions=[condition], max_items=max_items
        )

    def entry_get_favorites(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Favorite]:
        """
        List all favorites for the entry with the given ID.

        Convinience shorthand for `:py:method:.BotB.favorite_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param entry_id: ID of the entry to get favorites for.
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :returns: List of Favorite objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"entry_id": entry_id}
        if filters is not None:
            _filters = filters | _filters

        return self.favorite_list(
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
            max_items=max_items,
        )

    #
    # Favorites
    #

    def favorite_load(self, favorite_id: int) -> Union[Favorite, None]:
        """
        Load a favorite's info by their ID.

        :api: /api/v1/favorite/load
        :param favorite_id: ID of the favorite to load.
        :returns: Favorite object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("favorite", favorite_id)
        if ret is None:
            return None

        return Favorite.from_payload(ret)

    def _favorite_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Favorite]:
        """
        Search for favorites that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Favorite`.

        :api: /api/v1/favorite/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Favorite objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "favorite",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Favorite.from_payload(payload))

        return out

    def favorite_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Favorite]:
        """
        Search for favorites that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Favorite`.

        :api: /api/v1/favorite/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Favorite objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._favorite_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def favorite_random(self) -> Favorite:
        """
        Get a random favorite.

        :api: /api/v1/favorite/random
        :returns: Favorite object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("favorite")

        return Favorite.from_payload(ret)

    #
    # Formats
    #

    def format_load(self, format_id: int) -> Union[Format, None]:
        """
        Load a format's info by their ID.

        :api: /api/v1/format/load
        :param format_id: ID of the format to load.
        :returns: Format object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("format", format_id)
        if ret is None:
            return None

        return Format.from_payload(ret)

    def _format_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Format]:
        """
        Search for formats that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Format`.

        :api: /api/v1/format/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Format objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "format",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Format.from_payload(payload))

        return out

    def format_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Format]:
        """
        Search for formats that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Format`.

        :api: /api/v1/format/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Format objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._format_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def format_random(self) -> Format:
        """
        Get a random format.

        :api: /api/v1/format/random
        :returns: Format object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("format")

        return Format.from_payload(ret)

    #
    # Group threads
    #

    def group_thread_load(self, group_thread_id: int) -> Union[GroupThread, None]:
        """
        Load a group thread's info by their ID.

        :api: /api/v1/group_thread/load
        :param group_thread_id: ID of the group_thread to load.
        :returns: GroupThread object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("group_thread", group_thread_id)
        if ret is None:
            return None

        return GroupThread.from_payload(ret)

    def _group_thread_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[GroupThread]:
        """
        Search for group threads that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.GroupThread`.

        :api: /api/v1/group_thread/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of GroupThread objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "group_thread",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(GroupThread.from_payload(payload))

        return out

    def group_thread_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[GroupThread]:
        """
        Search for group threads that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.GroupThread`.

        :api: /api/v1/group_thread/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of GroupThread objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._group_thread_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def group_thread_random(self) -> GroupThread:
        """
        Get a random group thread.

        :api: /api/v1/group_thread/random
        :returns: GroupThread object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("group_thread")

        return GroupThread.from_payload(ret)

    def _group_thread_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[GroupThread]:
        """
        Search for group threads that match the given query.

        :api: /api/v1/group_thread/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of GroupThread objects representing the search results.
            If the search returned no results, the resulting iterable will return no
            results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "group_thread", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(GroupThread.from_payload(payload))

        return out

    def group_thread_search(
        self, query: str, max_items: int = 0
    ) -> Iterable[GroupThread]:
        """
        Search for group threads that match the given query.

        :api: /api/v1/group_thread/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of GroupThread objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._group_thread_search_noiter, query=query, max_items=max_items
        )

    #
    # Lyceum articles
    #

    def lyceum_article_load(self, lyceum_article_id: int) -> Union[LyceumArticle, None]:
        """
        Load a lyceum article's info by their ID.

        :api: /api/v1/lyceum_article/load
        :param lyceum_article_id: ID of the lyceum_article to load.
        :returns: LyceumArticle object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("lyceum_article", lyceum_article_id)
        if ret is None:
            return None

        return LyceumArticle.from_payload(ret)

    def _lyceum_article_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[LyceumArticle]:
        """
        Search for lyceum articles that match the given query (Non-PaginatedList
        version).

        For a list of supported filter/condition properties, see :py:class:`.LyceumArticle`.

        :api: /api/v1/lyceum_article/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of LyceumArticle objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "lyceum_article",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(LyceumArticle.from_payload(payload))

        return out

    def lyceum_article_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[LyceumArticle]:
        """
        Search for lyceum articles that match the given query (Non-PaginatedList
        version).

        For a list of supported filter/condition properties, see :py:class:`.LyceumArticle`.

        :api: /api/v1/lyceum_article/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of LyceumArticle objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._lyceum_article_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def lyceum_article_random(self) -> LyceumArticle:
        """
        Get a random lyceum article.

        :api: /api/v1/lyceum_article/random
        :returns: LyceumArticle object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("lyceum_article")

        return LyceumArticle.from_payload(ret)

    def _lyceum_article_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[LyceumArticle]:
        """
        Search for lyceum articles that match the given query.

        :api: /api/v1/lyceum_article/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of LyceumArticle objects representing the search
            results. If the search returned no results, the resulting iterable will
            return no results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "lyceum_article", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(LyceumArticle.from_payload(payload))

        return out

    def lyceum_article_search(
        self, query: str, max_items: int = 0
    ) -> Iterable[LyceumArticle]:
        """
        Search for lyceum articles that match the given query.

        :api: /api/v1/lyceum_article/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of LyceumArticle objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._lyceum_article_search_noiter, query=query, max_items=max_items
        )

    #
    # Palettes
    #

    def palette_load(self, palette_id: int) -> Union[Palette, None]:
        """
        Load a palette's info by their ID.

        :api: /api/v1/palette/load
        :param palette_id: ID of the palette to load.
        :returns: Palette object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("palette", palette_id)
        if ret is None:
            return None

        return Palette.from_payload(ret)

    def _palette_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Palette]:
        """
        Search for palettes that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Palette`.

        :api: /api/v1/palette/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Palette objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "palette",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Palette.from_payload(payload))

        return out

    def palette_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Palette]:
        """
        Search for palettes that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Palette`.

        :api: /api/v1/palette/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Palette objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._palette_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def palette_random(self) -> Palette:
        """
        Get a random palette.

        :api: /api/v1/palette/random
        :returns: Palette object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("palette")

        return Palette.from_payload(ret)

    def palette_current_default(self) -> Palette:
        """
        Get the current default on-site palette.

        :api: /api/v1/palette/current_default
        :returns: Palette object representing the current default palette.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get("https://battleofthebits.com/api/v1/palette/current_default")
        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            palette_json = ret.json()[0]
        except Exception as e:
            raise ConnectionError(ret.text) from e

        return Palette.from_payload(palette_json)

    #
    # Playlists
    #

    def playlist_load(self, playlist_id: int) -> Union[Playlist, None]:
        """
        Load a playlist's info by their ID.

        :api: /api/v1/playlist/load
        :param playlist_id: ID of the playlist to load.
        :returns: Playlist object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("playlist", playlist_id)
        if ret is None:
            return None

        return Playlist.from_payload(ret)

    def _playlist_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Playlist]:
        """
        Search for playlists that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Playlist`.

        :api: /api/v1/playlist/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Playlist objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "playlist",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Playlist.from_payload(payload))

        return out

    def playlist_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Playlist]:
        """
        Search for playlists that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Playlist`.

        :api: /api/v1/playlist/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Playlist objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._playlist_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def playlist_random(self) -> Playlist:
        """
        Get a random playlist.

        :api: /api/v1/playlist/random
        :returns: Playlist object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("playlist")

        return Playlist.from_payload(ret)

    def _playlist_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[Playlist]:
        """
        Search for playlists that match the given query.

        :api: /api/v1/playlist/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of Playlist objects representing the search results. If
            the search returned no results, the resulting iterable will return no
            results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "playlist", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Playlist.from_payload(payload))

        return out

    def playlist_search(self, query: str, max_items: int = 0) -> Iterable[Playlist]:
        """
        Search for playlists that match the given query.

        :api: /api/v1/playlist/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of Playlist objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._playlist_search_noiter, query=query, max_items=max_items
        )

    def playlist_to_entry_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[PlaylistToEntry]:
        """
        Perform a query against the playlist-to-entry table.

        In most cases, you don't need to use this function directly; instead, use
        `:py:method:.BotB.playlist_get_entries` or
        `:py:method:.BotB.entry_get_playlists`.

        :api: /api/v1/playlist_to_entry/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Playlist objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "playlist_to_entry",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(PlaylistToEntry.from_payload(payload))

        return out

    def playlist_get_entry_ids(self, playlist_id: int) -> List[int]:
        """
        Get a list containing the entry IDs of the playlist with the given ID, in the
        order that they appear in the playlist.

        To get a list of entry objects, see `:method:.BotBr.playlist_get_entries`.

        :param playlist_id: ID of the playlist to load the entries of.
        :returns: List of entry IDs.
        :raises ConnectionError: On connection error.
        """
        ret = PaginatedList(
            self.playlist_to_entry_list, filters={"playlist_id": playlist_id}
        )
        if not ret:
            return []

        return [p.entry_id for p in ret]

    def playlist_get_entries(self, playlist_id: int) -> List[Entry]:
        """
        Get a list containing a the entries in the playlist with the given ID, in the
        order that they appear in the playlist.

        :api: /api/v1/entry/playlist_playlist
        :param playlist_id: ID of the playlist to load the entries of.
        :returns: List of entry IDs.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/entry/playlist_playlist/{playlist_id}"
        )

        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            entries = ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

        out = []
        for entry in entries:
            out.append(Entry.from_payload(entry))
        return out

    #
    # Tags
    #

    def tag_load(self, tag_id: int) -> Union[Tag, None]:
        """
        Load a tag's info by their ID.

        :api: /api/v1/tag/load
        :param tag_id: ID of the tag to load.
        :returns: Tag object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("tag", tag_id)
        if ret is None:
            return None

        return Tag.from_payload(ret)

    def _tag_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Tag]:
        """
        Search for tags that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Tag`.

        :api: /api/v1/tag/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Tag objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "tag",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(Tag.from_payload(payload))

        return out

    def tag_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[Tag]:
        """
        Search for tags that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.Tag`.

        :api: /api/v1/tag/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of Tag objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._tag_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def tag_random(self) -> Tag:
        """
        Get a random tag.

        :api: /api/v1/tag/random
        :returns: Tag object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("tag")

        return Tag.from_payload(ret)

    def _tag_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[Tag]:
        """
        Search for tags that match the given query.

        :api: /api/v1/tag/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of Tag objects representing the search results. If the
            search returned no results, the resulting iterable will return no results.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "tag", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Tag.from_payload(payload))

        return out

    def tag_search(self, query: str, max_items: int = 0) -> Iterable[Tag]:
        """
        Search for tags that match the given query.

        :api: /api/v1/tag/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of Tag objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(self._tag_search_noiter, query=query, max_items=max_items)

    #
    # BotBr stats
    #

    def _botbr_stats_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[BotBrStats]:
        """
        Search for BotBr stats that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.BotBrStats`.

        :api: /api/v1/botbr_stats/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of BotBrStats objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "botbr_stats",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(BotBrStats.from_payload(payload))

        return out

    def botbr_stats_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[BotBrStats]:
        """
        Search for BotBr stats that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.BotBrStats`.

        :api: /api/v1/botbr_stats/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of BotBrStats objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._botbr_stats_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def botbr_stats_by_botbr_id(self, botbr_id: int) -> List[BotBrStats]:
        """
        Get a list of BotBrStats objects representing all of the BotBr's stats.

        Returns an empty list for nonexistent BotBrs.

        :api: /api/v1/botbr_stats/by_botbr_id
        :returns: List of BotBrStats objects representing the BotBr stats.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/botbr_stats/by_botbr_id/{botbr_id}"
        )

        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            stats = ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

        out = []
        for stat in stats:
            out.append(BotBrStats.from_payload(stat))
        return out

    def botbr_stats_days_back(self, botbr_id: int, n_days: int) -> List[BotBrStats]:
        """
        Get a list of BotBrStats objects representing the BotBr's stats from the last
        {n_days} days.

        Returns an empty list for nonexistent BotBrs.

        :api: /api/v1/botbr_stats/days_back
        :returns: List of BotBrStats objects representing the BotBr stats.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/botbr_stats/days_back/{botbr_id}/{n_days}"
        )

        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            stats = ret.json()
        except Exception as e:
            raise ConnectionError(ret.text) from e

        out = []
        for stat in stats:
            out.append(BotBrStats.from_payload(stat))
        return out

    def botbr_stats_random(self) -> BotBrStats:
        """
        Get a random BotBr stat.

        :api: /api/v1/botbr_stats/random
        :returns: BotBrStats object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("botbr_stats")

        return BotBrStats.from_payload(ret)

    #
    # Daily stats
    #

    def daily_stats_load(self, daily_stats_id: int) -> Union[DailyStats, None]:
        """
        Load a daily stat's info by their ID.

        :api: /api/v1/daily_stats/load
        :param daily_stats_id: ID of the daily_stats to load.
        :returns: DailyStats object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("daily_stats", daily_stats_id)
        if ret is None:
            return None

        return DailyStats.from_payload(ret)

    def _daily_stats_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[DailyStats]:
        """
        Search for daily stats that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.DailyStats`.

        :api: /api/v1/daily_stats/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of DailyStats objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        ret = self._list(
            "daily_stats",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append(DailyStats.from_payload(payload))

        return out

    def daily_stats_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[DailyStats]:
        """
        Search for daily stats that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.DailyStats`.

        :api: /api/v1/daily_stats/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of DailyStats objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        """
        return PaginatedList(
            self._daily_stats_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items,
        )

    def daily_stats_random(self) -> DailyStats:
        """
        Get a random daily stat.

        :api: /api/v1/daily_stats/random
        :returns: DailyStats object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("daily_stats")

        return DailyStats.from_payload(ret)


class BotBHacks(BotB):
    """
    Subclass of BotB object providing "hack" methods, i.e. methods based on parsed data
    from the site's frontend.

    This makes some data available that the API does not typically expose. Note
    that these functions can be unstable and may break at any point - use at your
    own risk!
    """

    # TODO: BotBr badge progress (botbr_get_badge_progress)
