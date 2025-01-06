# SPDX-License-Identifier: MIT
"""Dataclasses representing available object types and related enums."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
import pytz
from typing import (
    Dict,
    List,
    Optional,
    Self,
)
import re

try:  # Python >= 3.11
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum  # type: ignore

from .utils import unroll_payload, cached_property_dep


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
    #: (i.e. regular, bronze, silver, gold); see :py:enum:`.BadgeLevel`
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
    def from_payload(cls, payload: dict) -> Self:
        """
        Convert a JSON payload (provided as a dict) into a Format object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Format object.
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
    #: see :attr:`.Battle.end`.
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
    #:
    #: Some endpoints (e.g. Battle objects in :attr:`.Entry.battle`) do not
    #: return this value; in this case, use :func:`pybotb.botb.BotB.battle_load` to
    #: get the full battle info.
    period: Optional[BattlePeriod] = None

    #: String representing the date and time at which the battle ends, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: For major battles, this signifies the "final results" datetime;
    #: for the current battle period's end date, see :attr:`.period_end`.
    #:
    #: The end date is also converted to a datetime for developer convenience;
    #: see :attr:`.end`.
    period_end_str: Optional[str] = field(default=None)

    @cached_property_dep("period_end_str")
    def period_end(self) -> Optional[datetime]:
        """
        Date and time at which the current battle period ends.

        If :attr:`.period` is "vote", this signifies the period_end of the voting
        period.

        For the raw string, see :attr:`.period_end_str`.
        """
        if self.period_end_str is None:
            return None

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
        Convert a JSON payload (provided as a dict) into a Battle object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Battle object.
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
        Convert a JSON payload (provided as a dict) into an EntryAuthor object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting EntryAuthor object.
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
    authors: List[EntryAuthor]

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
        return f'<Entry: "{self.title}" by {self.authors_display} (Format {self.format_token}, Battle {self.battle.title}, ID {self.id})>'

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
        Convert a JSON payload (provided as a dict) into a Palette object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Palette object.
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
        Convert a JSON payload (provided as a dict) into a Playlist object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting Playlist object.
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
        Convert a JSON payload (provided as a dict) into a DailyStats object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting DailyStats object.
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
        return f"<DailyStats for {self.date_str} (ID {self.id})>"

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
        Convert a JSON payload (provided as a dict) into a BotBrStats object.

        :param payload: Dictionary containing the JSON payload.
        :returns: The resulting BotBrStats object.
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
