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

from .utils import Session, unroll_payload

#: Parser to use for BeautifulSoup; see:
#: https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser
SOUP_PARSER = "lxml"

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


# CODE NOTE:
#
# The order of "@property define, then matching dataclass attribute
# definition" is crucial. Explained with "aura" as an example:
#
# - The declaration of "aura" as a dataclass attribute is necessary
#   so that it can still be set in the init function (which we use
#   in BotBr.from_payload.
#
# - The @property define is used to clear the cache of some property
#   that depends on the overwritten property (e.g. aura is used to
#   calculate aura_url).
#
# - However, defining the property this way causes the property to
#   become an attribute with its default value being a "property
#   object"; then, dataclasses interprets it as a default value,
#   and does not let us declare non-default values afterwards.
#
# - To avoid this, we have to move the attribute definition *below*
#   the @property declaration, *and* set its default value to "field()"
#   to override the default value set by the @property declaration.
#
# - The variable docstring is set in the overriding attribute declaration
#   since Sphinx seems to look for it there.
#
# - The "internal storage" variable has a default set; otherwise, trying
#   to perform an equality comparison between two objects fails with an
#   AttributeError (honestly, this is probably a Python bug...)
#
# END CODE NOTE

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


@dataclass
class BotBr:
    """
    Represents a BotBr.

    Properties directly match API data, except where noted otherwise.
    """

    #: Internal storage for aura field; we overload the aura property to provide
    #: cache invalidation for aura_url.
    _aura: str = field(default="", init=False, repr=False)

    @property
    def aura(self) -> str:
        return self._aura

    @aura.setter
    def aura(self, aura: str):
        self._aura = aura
        try:
            del self.aura_url
        except AttributeError:
            pass

    #: String representing the aura PNG name for this BotBr; usually the BotBr ID zero-
    #: padded to 8 characters.
    #:
    #: This is used to calculate the aura URL in :attr:`.BotBr.aura_url`.
    aura: str = field()

    #: Fallback color for the aura, as a hex value (#ffffff).
    aura_color: str

    @cached_property
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

    #: Internal storage for create_date_str field; we overload the create_date_str
    #: property to provide cache invalidation for create_date.
    _create_date_str: str = field(default="", init=False, repr=False)

    @property
    def create_date_str(self) -> str:
        return self._create_date_str

    @create_date_str.setter
    def create_date_str(self, create_date_str: str):
        self._create_date_str = create_date_str
        try:
            del self.create_date
        except AttributeError:
            pass

    #: String representing the creation date of the BotBr's account, in YYYY-MM-DD
    #: format, in the US East Coast timezone (same as all other dates on-site).
    #:
    #: The creation date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.create_date`.
    create_date_str: str = field()

    @cached_property
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

    #: Internal storage for laston_date_str field; we overload the laston_date_str
    #: property to provide cache invalidation for laston_date.
    _laston_date_str: str = field(default="", init=False, repr=False)

    @property
    def laston_date_str(self) -> str:
        return self._laston_date_str

    @laston_date_str.setter
    def laston_date_str(self, laston_date_str: str):
        self._laston_date_str = laston_date_str
        try:
            del self.laston_date
        except AttributeError:
            pass

    #: String representing the date on which the BotBr was last seen on the site, in
    #: YYYY-MM-DD format, in the US East Coast timezone (same as all other dates on-
    #: site).
    #:
    #: The last-on date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.laston_date`.
    laston_date_str: str = field()

    @cached_property
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

    #: Two-letter country code of the BotBr. For a list, see TODO.
    #:
    #: Note that this property is not typically returned by the API; it is only
    #: available through entry author listings. You can use
    #: `:py:method:.BotB.botbr_fill_country` to fetch it on a regular BotBr object
    #: (that function also supports bulk operations).
    country_code: str = "xx"

    #: Name of the BotBr's country. For a list, see TODO.
    #:
    #: Note that this property is not typically returned by the API; it is only
    #: available through entry author listings. You can use
    #: `:py:method:.BotB.botbr_fill_country` to fetch it on a regular BotBr object
    #: (that function also supports bulk operations).
    country_name: str = "unknown"

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


class Medium(Enum):
    """Enum for different medium types; not to be confused with formats."""

    INVALID = 0
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

    #: Internal storage for type field; we overload the type property
    #: to provide cache invalidation for is_xhb.
    _type: int = field(default="", init=False, repr=False)

    @property
    def type(self) -> int:
        return self._type

    @type.setter
    def type(self, type: int):
        self._type = type
        try:
            del self.is_xhb
        except AttributeError:
            pass

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

    @cached_property
    def is_xhb(self) -> bool:
        """
        Whether or not this battle is an X Hour Battle/minor battle.

        :returns: True if the battle is an XHB, False otherwise.
        """
        return self.type == 3

    #: Amount of entries submitted.
    entry_count: int

    #: Internal storage for start_str field; we overload the start_str
    #: property to provide cache invalidation for start_date.
    _start_str: str = field(default="", init=False, repr=False)

    @property
    def start_str(self) -> str:
        return self._start_str

    @start_str.setter
    def start_str(self, start_str: str):
        self._start_str = start_str
        try:
            del self.start
        except AttributeError:
            pass

    #: String representing the date and time at which the battle starts, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: The start date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.start_date`.
    start_str: str = field()

    @cached_property
    def start(self) -> datetime.datetime:
        """
        Last seen date as a datetime object.

        For the raw string, see :attr:`.BotBr.start_str`.
        """
        return datetime.strptime(self.start_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    #: Internal storage for end_str field; we overload the end_str
    #: property to provide cache invalidation for end_date.
    _end_str: str = field(default="", init=False, repr=False)

    @property
    def end_str(self) -> str:
        return self._end_str

    @end_str.setter
    def end_str(self, end_str: str):
        self._end_str = end_str
        try:
            del self.end
        except AttributeError:
            pass

    #: String representing the date and time at which the battle ends, in
    #: YYYY-MM-DD HH:MM:SS format, in the US East Coast timezone (same as all
    #: other dates on the site).
    #:
    #: The end date is also converted to a datetime for developer convenience;
    #: see :attr:`.BotBr.end_date`.
    end_str: str = field()

    @cached_property
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

    #: Internal storage for datetime_str field; we overload the datetime_str
    #: property to provide cache invalidation for datetime.
    _datetime_str: str = field(default="", init=False, repr=False)

    @property
    def datetime_str(self) -> str:
        return self._datetime_str

    @datetime_str.setter
    def datetime_str(self, datetime_str: str):
        self._datetime_str = datetime_str
        try:
            del self.datetime
        except AttributeError:
            pass

    #: String representing the submission date of this entry in YYYY-MM-DD
    #: HH:MM:SS format, in the US East Coast timezone (same as all other dates
    #: on the site).
    #:
    #: The creation date is also converted to a datetime for developer convenience;
    #: see :attr:`.Entry.datetime`.
    datetime_str: str = field()

    @cached_property
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

    #: Relative player URL for the entry ("/player/Entry/{id}" format).
    #:
    #: Present for all entries, including those without a valid player (i.e.
    #: non-audio entries).
    listen_url: str

    #: Medium of the entry; see :py:enum:`.Medium` for possible values.
    #:
    #: This is consolidated from "medium_*" variables ("medium_audio", "medium_visual",
    #: etc.)
    medium: Medium

    #: Amount of comments ("posts") under this entry.
    posts: int

    #: ???
    q: int

    #: Rank of the entry.
    rank: int

    #: English plural suffix for the rank (e.g "st" for 1st, "nd" for 2nd, etc.)
    rank_suffix: str

    #: HTML representation of rank; likely not of use to implementations.
    rank_display: str

    #: Score of the entry.
    score: float

    #: HTML representation of score; likely not of use to implementations.
    score_display: str

    #: The entry's title.
    title: str

    #: Relative URL to the entry thumbnail; empty for entries without a
    #: thumbnail (i.e. non-visual entries).
    thumbnail_url: str

    #: HTML representation of trophies this entry has.
    #: TODO: make a custom prop out of this
    trophy_display: str

    #: Amount of votes this entry got.
    votes: int

    #: Length of the entry, in seconds.
    #:
    #: Only present for audio entries.
    length: float = 0

    #: Direct URL to the source file of an audio entry.
    #:
    #: None for non-audio entries. (The API returns False for non-audio entries;
    #: we turn it to None for API convenience.)
    play_url: Optional[str] = None

    #: YouTube URL for this entry, if any.
    youtube_url: Optional[str] = None

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

        ret = unroll_payload(cls, payload_parsed)
        ret._raw_payload = payload.copy()

        return ret

    def __repr__(self):
        return f'<Entry: "{self.name}" by {self.botbr.name} (Format {self.format_token}, Battle {self.battle.name}, ID {self.id})>'


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


@dataclass
class Tag:
    """A tag on an entry."""

    #: ID of the tag.
    id: int

    #: ID of the entry this tag applies to.
    entry_id: int

    #: The tag applied to the entry.
    tag: str

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
        return f"<Tag \"{self.tag}\" on entry {self.entry_id} (ID {self.id})>"


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

    def __init__(self):
        #: Internal Session object.
        self._s = Session()

    # Common API methods

    def _load(self, object_type: str, object_id: int) -> Union[dict, None]:
        """
        Load information about an object with the given type and ID.

        This function is primarily used internally; for API users, use one of
        the load_{object_type}_* functions instead.

        :param object_type: Object type string.
        :param object_id: ID of the object.
        :returns: A dictionary containing the JSON result, or None if not found.
        :raises ConnectionError: On connection error.
        """
        # TODO - API returns 500 on not found instead of 404, prompting a retry.
        # Find a way to jack into requests to fix this.
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/{object_type}/load/{object_id}"
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

        This function is primarily used internally; for API users, use one of
        the load_{object_type}_* functions instead.

        :param object_type: Object type string.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
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
            print({"conditions": [c.to_dict() for c in conditions]})
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

    def _search(self, object_type: str, query: str) -> Union[dict, None]:
        """
        Search for objects with the given object type using the provided query.

        The query is checked against the title/name of the object; if an object
        matches, it is included in the results.

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

    def _random(self, object_type: str) -> Union[dict, None]:
        """
        Get random item of the given object type.

        This function is primarily used internally; for API users, use one of
        the get_{object_type}_* functions instead.

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

    def list_iterate_over_pages(
        self,
        list_func: Callable,
        sort: str,
        max_items: int = 0,
        desc: bool = False,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Any]:
        """
        Call the specified list function and iterate over all pages. A sort key is
        required to make sure the results are returned correctly.

        :param list_func: List function, e.g. `:py:method:.BotB.botbr_list`, etc.
        :param sort: Object property to sort by.
        :param max_items: Limit how many items to fetch. 0 means no limit.
        :param desc: If True, returns items in descending order.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
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

    # BotBr

    def botbr_load(self, botbr_id: int) -> Union[BotBr, None]:
        """
        Load a BotBr's info by their ID.

        :returns: BotBr object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("botbr", botbr_id)
        if not ret:
            return None

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

    #
    # Entry
    #

    def entry_fillup(self, entry: Entry, authors_full: bool = False):
        """
        Common function that performs a few "fill-ups" for fetched entries, according to
        user parameters.

        In most cases, you will not need to use this directly; all of the relevant API
        methods provide the same parameters, and pass them to this function. It is left
        public primarily for documentation.

        Note that this function performs all operations in-place.

        :param authors_full: Fetch full information about all authors. By default, the
            BotB API only returns limited information about entry authors other than the
            main submitter. If you need the full BotBr data of *all* entry
            collaborators, setting this to True will cause pyBotB to send out a fetch to
            get the info of every BotBr in the authors list, and fill in the data.
        :returns: The modified Entry object. Note that this function also performs all
            operations in-place.
        :raises ConnectionError: On connection error (if authors_full is True).
        """
        if authors_full:
            author_ids = set([a.id for a in entry.authors])

            botbrs = []
            i = author_ids
            n = 0
            while i > 0:
                botbrs += self.botbr_list(
                    page_number=n,
                    page_length=i % 250,
                    sort="id",
                    conditions=[
                        Condition("id", "IN", "(" + ",".join(author_ids) + ")")
                    ],
                )
                i -= 250
                n += 1

            # TODO match botbr to id

        return entry

    def entry_load(
        self, entry_id: int, authors_full: bool = False
    ) -> Union[Entry, None]:
        """
        Load an entry's info by its ID.

        :param authors_full: Fetch full information about all authors.
        :returns: entry object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._load("entry", entry_id)
        if not ret:
            return None

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

    #
    # Favorites
    #

    def favorite_load(self, favorite_id: int) -> Union[Favorite, None]:
        """
        Load a favorite's info by its ID.

        :param authors_full: Fetch full information about all authors.
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

    def favorite_list_for_entry(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Favorite]:
        """
        List all favorites for the entry with the given ID.

        Convinience shorthand for `:py:method:.BotB.favorite_list` which pre-fills
        the filters to search for the entry and automatically aggregates all
        results pages.

        :param entry_id: ID of the entry to get favorites for.
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

    def favorite_list_for_botbr(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Favorite]:
        """
        List all favorites given by the BotBr with the given ID.

        Convinience shorthand for `:py:method:.BotB.favorite_list` which pre-fills
        the filters to search for the entry and automatically aggregates all
        results pages.

        :param entry_id: ID of the entry to get favorites for.
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

    #
    # Tags
    #

    def tag_load(self, tag_id: int) -> Union[Tag, None]:
        """
        Load a tag's info by its ID.

        :param authors_full: Fetch full information about all authors.
        :returns: Tag object representing the user, or None if the user is not
            found.
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

    # TODO: tag/cloud_by_substring/XXX

    def tag_list_for_entry(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[Tag]:
        """
        List all tags for the entry with the given ID.

        Convinience shorthand for `:py:method:.BotB.tag_list` which pre-fills
        the filters to search for the entry and automatically aggregates all
        results pages.

        :param entry_id: ID of the entry to get tags for.
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


class BotBHacks(BotB):
    """
    Subclass of BotB object providing "hack" methods, i.e. methods based on parsed data
    from the site's frontend.

    This makes some data available that the API does not typically expose. Note
    that these functions can be unstable and may break at any point - use at your
    own risk!
    """

    # TODO: BotBr badge progress (botbr_get_badge_progress)
