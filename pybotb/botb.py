# SPDX-License-Identifier: MIT
"""Code for interfacing with BotB."""

from functools import cached_property
import dataclasses
from dataclasses import dataclass, field
import datetime
from enum import Enum
import pytz
from typing import cast, Any, Callable, Dict, List, Optional, TypedDict, Union, Self
from urllib.parse import quote, urlencode

from . import VERSION
from .utils import Session, unroll_payload, int_list_to_sql, cached_property_dep

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


class BadgeLevel(Enum):
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
    def create_date(self) -> datetime.datetime:
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
    def laston_date(self) -> datetime.datetime:
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


class Medium(Enum):
    """
    Enum for different medium types; not to be confused with formats.

    The numerical values are pyBotB-specific; on the Entry, object, this value
    is derived from "medium_audio", "medium_visual", etc. properties of the API.
    """

    UNKNOWN = 0
    AUDIO = 1
    VISUAL = 2
    # TODO


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
        ret = unroll_payload(cls, payload)
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f"<Format: {self.title} ({self.token}) (ID {self.id})>"

    def __str__(self):
        return self.__repr__()


@dataclass
class Battle:
    """Represents a battle."""

    #: ID of the battle.
    id: int

    #: Title of the battle.
    title: str

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
    #: see :attr:`.BotBr.start_date`.
    start_str: str

    @cached_property_dep("start_str")
    def start(self) -> datetime.datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see :attr:`.BotBr.start_str`.
        """
        return datetime.strptime(self.start_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: String representing the date and time at which the battle ends, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: The end date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.end_date`.
    end_str: str = field()

    @cached_property_dep("end_str")
    def end(self) -> datetime.datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see :attr:`.BotBr.end_str`.
        """
        return datetime.strptime(self.end_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: List of format tokens for this battle. For XHBs, this will contain one
    #: item; for majors, there may be more formats.
    format_tokens: List[str]

    # TODO check if this is returned
    disable_penalty: bool = False

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

        ret = unroll_payload(
            cls,
            payload_parsed,
            payload_to_attr={
                "start": "start_str",
                "end": "end_str",
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
    Represents an entry author, as returned in the "authors" field of the entry API.
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
    def datetime(self) -> datetime.datetime:
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

    #: Amount of comments ("posts") under this entry.
    posts: int

    #: ???
    q: int

    #: The entry's title.
    title: str

    #: Relative URL to the entry thumbnail; empty for entries without a
    #: thumbnail (i.e. non-visual entries).
    thumbnail_url: str

    #: Amount of votes this entry got.
    votes: int

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
            payload_parsed["medium"] = Medium.UNKNOWN

        # HACK: some old entries from 2009 are broken and have null posts
        # (e.g. all entries in https://battleofthebits.com/arena/Battle/335/MainScreen/themed+allgear+-+internet+power+struggle).
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
        return f'<Entry: "{self.name}" by {self.botbr.name} (Format {self.format_token}, Battle {self.battle.name}, ID {self.id})>'

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

    #: URL to the palette CSS.
    #:
    #: This is a CSS file hosted on battleofthebits.com which contains a
    #: :root directive with the colors as CSS variables. Each color has its
    #: hex code stored in the --colorX variable, with the individual RGB
    #: components stored in --colorX_r, --colorX_g and --colorX_b for red,
    #: green and blue respectively.
    #:
    #: This variable is derived from the ID.
    @property
    def css_url(self):
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
    #: see :attr:`.BotBr.date_create`.
    date_create_str: str

    @cached_property_dep("date_create_str")
    def date_create(self) -> datetime.datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see
        :attr:`.BotBr.date_create_str`.
        """
        return datetime.strptime(self.date_create_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: String representing the date on which the BotBr was last seen on the site, in
    #: YYYY-MM-DD format, in the US East Coast timezone (same as all other dates on-
    #: site).
    #:
    #: The last-on date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.date_modify`.
    date_modify_str: str = field()

    @cached_property_dep("date_modify_str")
    def date_modify(self) -> datetime.datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see
        :attr:`.BotBr.date_modify_str`.
        """
        return datetime.strptime(self.date_modify_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: Description of the playlist.
    description: Optional[str] = None

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
    """
    Link between playlist and entry returned by the playlist_to_entry API.
    """

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


@dataclass(slots=True)
class Condition:
    """Represents a condition passed to a "list" API query."""

    #: Property that the condition applies to.
    property: str

    #: Operator for the condition.
    operator: str

    #: Operand for the condition.
    operand: str

    def to_dict(self) -> dict:
        """
        Return the condition as a dictionary that can be passed to the list API.

        :returns: The condition represented as a dictionary.
        """
        return dataclasses.asdict(self)


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

        :param app_name: App name to be used in the user agent for requests;
                         see `:attr:.app_name`.
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
            handle_notfound=True
        )
        if ret.status_code == 404:
            return None
        elif ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            return ret.json()
        except:
            raise ConnectionError(ret.text)

    def _list(
        self,
        object_type: str,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> Union[dict, None]:
        """
        Load information about an object with the given type and ID.

        This function is primarily used internally; for API users, use one of the
        load_{object_type}_* functions instead.

        :param object_type: Object type string.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: A dictionary containing the JSON result, or None if not found.
        :raises ConnectionError: On connection error.
        """
        if page_length > 250:
            raise ValueError("Maximum page length is 250")

        url = f"https://battleofthebits.com/api/v1/{object_type}/list/{page_number}/{page_length}"
        params = {}
        if desc:
            params["desc"] = str(desc).lower()
        if sort:
            params["sort"] = sort

        if filters:
            filter_str = ""
            for fkey, fval in filters.items():
                filter_str += f"^{fkey}~{fval}"
            filter_str = filter_str[1:]
            params["filters"] = filter_str

        if params:
            url += "?" + urlencode(params)

        if conditions:
            ret = self._s.post(
                url, json={"conditions": [c.to_dict() for c in conditions]}
            )
        else:
            ret = self._s.get(url)

        if ret.status_code == 400 and "Please RTFM" in ret.text:
            raise ValueError(ret.text.split("\n")[0])

        if not ret.text:
            return []

        try:
            return ret.json()
        except:
            raise ConnectionError(ret.text)

    def _random(self, object_type: str) -> Union[dict, None]:
        """
        Get random item of the given object type.

        This function is primarily used internally; for API users, use one of the
        get_{object_type}_* functions instead.

        :param object_type: Object type string.
        :returns: A dictionary containing the JSON result, or None if not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(f"https://battleofthebits.com/api/v1/{object_type}/random")
        if ret.status_code == 404:
            return None

        try:
            return ret.json()[0]
        except:
            raise ConnectionError(ret.text)

    def _search(self, object_type: str, query: str) -> Union[dict, None]:
        """
        Search for objects with the given object type using the provided query.

        The query is checked against the title/name of the object; if an object matches,
        it is included in the results.

        :param object_type: Object type string.
        :param query: String to query for.
        :returns: A dictionary containing the JSON result, or None if not found.
        :raises ConnectionError: On connection error.
        """
        query_enc = quote(query, safe="")

        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/{object_type}/search/{query_enc}"
        )
        if ret.status_code == 404:
            return None

        try:
            return ret.json()
        except:
            raise ConnectionError(ret.text)

    def list_iterate_over_pages(
        self,
        list_func: Callable,
        max_items: int = 0,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Any]:
        """
        Call the specified list function and iterate over all pages. A sort key is
        required to make sure the results are returned correctly.

        :param list_func: List function, e.g. `:py:method:.BotB.botbr_list`, etc.
        :param max_items: Limit how many items to fetch. 0 means no limit.
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by. Recommended.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: A list of all found objects, converted to the type returned by
            list_func.
        :raises ConnectionError: On connection error.
        """
        out = []
        n_items = 0
        page = 0

        while True:
            ret = list_func(
                page_number=page,
                page_length=250,
                desc=desc,
                sort=sort,
                filters=filters,
                conditions=conditions,
            )
            out += ret

            page += 1
            n_items += len(ret)

            if (max_items > 0 and n_items < max_items) or len(ret) < 250:
                break

        return out

    # BotBr

    def botbr_load(self, botbr_id: int) -> Union[BotBr, None]:
        """
        Load a BotBr's info by their ID.

        :param botbr_id: ID of the botbr to load.
        :returns: BotBr object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("botbr", botbr_id)
        if not ret:
            return None

        return BotBr.from_payload(ret)

    def botbr_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[BotBr]:
        """
        Search for BotBrs that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.BotBr`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of BotBr objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def botbr_random(self) -> BotBr:
        """
        Get a random BotBr.

        :returns: BotBr object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("botbr")

        return BotBr.from_payload(ret)

    def botbr_search(self, query: str) -> List[BotBr]:
        """
        Search for BotBrs that match the given query.

        :param query: Search query for the search.
        :returns: List of BotBr objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search("botbr", query)

        out = []
        for payload in ret:
            out.append(BotBr.from_payload(payload))

        return out

    def botbr_get_id_for_username(self, username: str) -> Union[int, None]:
        """
        Get the ID of a BotBr by their username.

        :param username: Username of the BotBr to find the ID of.
        :returns: int containing the ID, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self.botbr_search(username)
        if not ret:
            return None

        for user in ret:
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
        ret = self.botbr_search(username)
        if not ret:
            return None

        return ret[0]

    def botbr_get_favorites(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Favorite]:
        """
        List all favorites given by the BotBr with the given ID.

        Convinience shorthand for `:py:method:.BotB.favorite_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param entry_id: ID of the entry to get favorites for.
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Favorite objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"botbr_id": botbr_id}
        if filters:
            _filters = filters | {_filters}

        return self.list_iterate_over_pages(
            self.favorite_list,
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
        )

    def botbr_get_palettes(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Palette]:
        """
        List all palettes created by the BotBr with the given ID.

        Convinience shorthand for `:py:method:.BotB.palette_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param entry_id: ID of the entry to get palettes for.
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Palette objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"botbr_id": botbr_id}
        if filters:
            _filters = filters | {_filters}

        return self.list_iterate_over_pages(
            self.palette_list,
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
        )

    #
    # Entry
    #

    def entry_load(self, entry_id: int) -> Union[Entry, None]:
        """
        Load an entry's info by its ID.

        :param entry_id: ID of the entry to load.
        :param authors_full: Fetch full information about all authors.
        :returns: entry object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("entry", entry_id)
        if not ret:
            return None

        return Entry.from_payload(ret)

    def entry_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Entry]:
        """
        Search for entries that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Entry`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of entry objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def entry_random(self) -> Entry:
        """
        Get a random entry.

        :returns: entry object representing the user.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("entry")

        return Entry.from_payload(ret)

    def entry_search(self, query: str) -> List[Entry]:
        """
        Search for entries that match the given query.

        :param query: Search query for the search.
        :returns: List of entry objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search("entry", query)

        out = []
        for payload in ret:
            out.append(Entry.from_payload(payload))

        return out

    def entry_get_tags(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Tag]:
        """
        List all tags given to entry with the given ID.

        Convinience shorthand for `:py:method:.BotB.tag_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param entry_id: ID of the entry to get tags for.
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Tag objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"entry_id": entry_id}
        if filters:
            _filters = filters | {_filters}

        return self.list_iterate_over_pages(
            self.tag_list,
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
        )

    def entry_get_playlist_ids(self, entry_id: int) -> List[int]:
        """
        Get a list containing the playlist IDs of playlists that this entry
        has been added to.

        To get a list of Playlist objects, see `:method:.BotBr.entry_get_playlists`.

        :param entry_id: ID of the entry to load the playlists of.
        :returns: List of playlist IDs.
        :raises ConnectionError: On connection error.
        """
        ret = self.list_iterate_over_pages(
            self.playlist_to_entry_list, filters={"entry_id": entry_id}
        )
        if not ret:
            return []

        return [p.playlist_id for p in ret]

    def entry_get_playlists(self, entry_id: int) -> List[Playlist]:
        """
        Get a list of playlists that this entry has been added to.

        :param entry_id: ID of the playlist to load the entries of.
        :returns: List of Playlist objects.
        :raises ConnectionError: On connection error.
        """
        playlist_ids = self.entry_get_playlist_ids(entry_id)

        condition = Condition("playlist_id", "IN", int_list_to_sql(playlist_ids))

        return self.list_iterate_over_pages(
            self.playlist_list, sort="id", conditions=[condition]
        )

    def entry_get_favorites(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Favorite]:
        """
        List all favorites for the entry with the given ID.

        Convinience shorthand for `:py:method:.BotB.favorite_list` which pre-fills the
        filters to search for the entry and automatically aggregates all results pages.

        :param entry_id: ID of the entry to get favorites for.
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Favorite objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _filters = {"entry_id": entry_id}
        if filters:
            _filters = filters | {_filters}

        return self.list_iterate_over_pages(
            self.favorite_list,
            sort=sort or "id",
            desc=desc,
            filters=_filters,
            conditions=conditions,
        )

    #
    # Battles
    #

    def battle_load(self, battle_id: int) -> Union[Battle, None]:
        """
        Load a battle's info by its ID.

        :param botbr_id: ID of the battle to load.
        :returns: Battle object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("battle", battle_id)
        if not ret:
            return None

        return Battle.from_payload(ret)

    def battle_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Battle]:
        """
        Search for battles that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Battle`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Battle objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def battle_random(self) -> Battle:
        """
        Get a random battle.

        :returns: Battle object representing the battle.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("battle")

        return Battle.from_payload(ret)

    def battle_search(self, query: str) -> List[Battle]:
        """
        Search for battles that match the given query.

        :param query: Search query for the search.
        :returns: List of Battle objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search("battle", query)

        out = []
        for payload in ret:
            out.append(Battle.from_payload(payload))

        return out

    #
    # Favorites
    #

    def favorite_load(self, favorite_id: int) -> Union[Favorite, None]:
        """
        Load a favorite's info by its ID.

        :param botbr_id: ID of the favorite to load.
        :returns: Favorite object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("favorite", favorite_id)
        if not ret:
            return None

        return Favorite.from_payload(ret)

    def favorite_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Favorite]:
        """
        Search for favorites that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Favorite`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Favorite objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def favorite_random(self) -> Favorite:
        """
        Get a random favorite.

        :returns: Favorite object representing the favorite.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("favorite")

        return Favorite.from_payload(ret)

    #
    # Tags
    #

    def tag_load(self, tag_id: int) -> Union[Tag, None]:
        """
        Load a tag's info by its ID.

        :param botbr_id: ID of the tag to load.
        :returns: Tag object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("tag", tag_id)
        if not ret:
            return None

        return Tag.from_payload(ret)

    def tag_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Tag]:
        """
        Search for tags that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Tag`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Tag objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def tag_random(self) -> Tag:
        """
        Get a random tag.

        :returns: Tag object representing the tag.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("tag")

        return Tag.from_payload(ret)

    def tag_search(self, query: str) -> List[Tag]:
        """
        Search for tags that match the given query.

        :param query: Search query for the search.
        :returns: List of Tag objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search("tag", query)

        out = []
        for payload in ret:
            out.append(Tag.from_payload(payload))

        return out

    #
    # Palettes
    #

    def palette_load(self, palette_id: int) -> Union[Palette, None]:
        """
        Load a palette's info by its ID.

        :param botbr_id: ID of the palette to load.
        :returns: Palette object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("palette", palette_id)
        if not ret:
            return None

        return Palette.from_payload(ret)

    def palette_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Palette]:
        """
        Search for palettes that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Palette`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Palette objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def palette_random(self) -> Palette:
        """
        Get a random palette.

        :returns: Palette object representing the palette.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("palette")

        return Palette.from_payload(ret)

    def palette_current_default(self) -> Palette:
        """
        Get the current default on-site palette.

        :returns: Palette object representing the current default palette.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(f"https://battleofthebits.com/api/v1/palette/current_default")
        if ret.status_code != 200:
            raise ConnectionError(f"{ret.status_code}: {ret.text}")

        try:
            palette_json = ret.json()[0]
        except:
            raise ConnectionError(ret.text)

        return Palette.from_payload(palette_json)

    #
    # Formats
    #

    def format_load(self, format_id: int) -> Union[Format, None]:
        """
        Load a format's info by its ID.

        :param botbr_id: ID of the format to load.
        :returns: Format object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("format", format_id)
        if not ret:
            return None

        return Format.from_payload(ret)

    def format_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Format]:
        """
        Search for formats that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Format`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Format objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def format_random(self) -> Format:
        """
        Get a random format.

        :returns: Format object representing the format.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("format")

        return Format.from_payload(ret)

    #
    # Playlists
    #

    def playlist_load(self, playlist_id: int) -> Union[Playlist, None]:
        """
        Load a playlist's info by its ID.

        :param playlist_id: ID of the playlist to load.
        :returns: Playlist object representing the user, or None if the user is not
            found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("playlist", playlist_id)
        if not ret:
            return None

        return Playlist.from_payload(ret)

    def playlist_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Playlist]:
        """
        Search for playlists that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Playlist`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Playlist objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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

    def playlist_random(self) -> Playlist:
        """
        Get a random playlist.

        :returns: Playlist object representing the playlist.
        :raises ConnectionError: On connection error.
        """
        ret = self._random("playlist")

        return Playlist.from_payload(ret)

    def playlist_to_entry_list(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[PlaylistToEntry]:
        """
        Perform a query against the playlist-to-entry table.

        In most cases, you don't need to use this function directly; instead,
        use `:py:method:.BotB.playlist_get_entries` or
        `:py:method:.BotB.entry_get_playlists`.

        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of Playlist objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
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
        Get a list containing the entry IDs of the playlist with the given ID,
        in the order that they appear in the playlist.

        To get a list of entry objects, see `:method:.BotBr.playlist_get_entries`.

        :param playlist_id: ID of the playlist to load the entries of.
        :returns: List of entry IDs.
        :raises ConnectionError: On connection error.
        """
        ret = self.list_iterate_over_pages(
            self.playlist_to_entry_list, filters={"playlist_id": playlist_id}
        )
        if not ret:
            return []

        return [p.entry_id for p in ret]

    def playlist_get_entries(self, playlist_id: int, max_items: int = 0) -> List[Entry]:
        """
        Get a list containing a the entries in the playlist with the given ID,
        in the order that they appear in the playlist.

        :param playlist_id: ID of the playlist to load the entries of.
        :returns: List of entry IDs.
        :raises ConnectionError: On connection error.
        """
        entry_ids = self.playlist_get_entry_ids(playlist_id)

        condition = Condition("entry_id", "IN", int_list_to_sql(entry_ids))

        entries = dict(
            [
                (e.id, e)
                for e in self.list_iterate_over_pages(
                    self.entry_list, sort="id", conditions=[condition]
                )
            ]
        )

        ret = []
        for entry_id in entry_ids:
            ret.append(entries[entry_id])

        return ret


class BotBHacks(BotB):
    """
    Subclass of BotB object providing "hack" methods, i.e. methods based on parsed data
    from the site's frontend.

    This makes some data available that the API does not typically expose. Note
    that these functions can be unstable and may break at any point - use at your
    own risk!
    """

    # TODO: BotBr badge progress (botbr_get_badge_progress)
