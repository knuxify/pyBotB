# SPDX-License-Identifier: MIT
"""Code for interfacing with BotB."""

from bs4 import BeautifulSoup
import dataclasses
from dataclasses import dataclass
from datetime import date as dt_date, datetime
from functools import cached_property
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Tuple,
    Optional,
    Union,
)
from urllib.parse import quote, urlencode

from . import VERSION
from .types import (
    Battle,
    BotBr,
    Entry,
    Favorite,
    Format,
    GroupThread,
    LyceumArticle,
    Palette,
    Playlist,
    PlaylistToEntry,
    Tag,
    BotBrStats,
    DailyStats,
)
from .utils import Session, param_stringify


@dataclass
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

    def __init__(
        self, func: Callable, max_items: int = 0, offset: int = 0, *args, **kwargs
    ):
        """
        Initialize a paginated iterator.

        :param func: List function to call; must take page_number and page_length
            values.
        :param offset: Skip the first N items.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param args: Arguments to pass to the list function.
        :param kwargs: Keyword arguments to pass to the list function.
        """
        self.func = func
        self.offset = offset
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

        if self.offset:
            count = self.offset
            page = self.offset // page_length
            index = self.offset % page_length

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


def parse_tag_cloud(cloud_html: str) -> Dict[str, int]:
    """
    Parse tag cloud HTML (as returned by the /api/v1/tag/cloud_by_substring API) into a
    dictionary containing the tag as the key and the size as the value.

    :param cloud_html: HTML to parse, as a string.
    :returns: Dictionary with tag as the key and size in pixels as the value.
    """
    soup = BeautifulSoup(cloud_html, "lxml")

    out = {}
    for tag_a in soup.find_all("a"):
        out[tag_a.text.replace(r"<\/a>", "").strip()] = int(
            "".join([a for a in tag_a["style"].split("font-size:")[1] if a.isnumeric()])
        )

    return out


class BotB:
    """
    BotB API class.

    Exposes access to the official BotB API, documented on the
    Lyceum (https://battleofthebits.com/lyceum/View/BotB+API+v1).
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
        offset: int = 0,
    ) -> Iterable[BotBr]:
        """
        Search for BotBrs that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.BotBr`.

        :api: /api/v1/botbr/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of BotBr objects representing the search results.
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
            offset=offset,
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
        :returns: List of BotBr objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "botbr", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(BotBr.from_payload(payload))

        return out

    def botbr_search(
        self, query: str, max_items: int = 0, offset: int = 0
    ) -> Iterable[BotBr]:
        """
        Search for BotBrs that match the given query.

        :api: /api/v1/botbr/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of BotBr objects representing the search results. If the
            search returned no results, the resulting iterable will return no results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._botbr_search_noiter, query=query, max_items=max_items, offset=offset
        )

    @cached_property
    def botbr_levels(self) -> List[int]:
        """
        List of level-up steps for a BotBr, from level 0 to 34 (the maximum).

        :api: /api/v1/botbr/levels
        """
        ret = self._s.get("https://battleofthebits.com/api/v1/botbr/levels")

        return ret.json()

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

    def botbr_get_entries(
        self,
        botbr_id: int,
        submitted_only: bool = False,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[Entry]:
        """
        List all entries which the BotBr authored (i.e. both entries submitted by the
        BotBr and entries where they were tagged as a collaborator).

        For only entries submitted by the BotBr, set submitted_only to True.

        :api: /api/v1/entry/botbr_favorites_playlist
        :param botbr_id: ID of the BotBr to get favorites for.
        :param submitted_only: If True, returns only entries submitted by this BotBr directly,
            excluding collaborations.
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: `PaginatedList` of Entry objects representing the list results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _conditions = [Condition("id", "IN_SUBQUERY:botbr_entry_list", botbr_id)]
        if submitted_only:
            _conditions.append(Condition("botbr_id", "=", botbr_id))
        if conditions:
            _conditions = conditions | _conditions

        return self.entry_list(
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=_conditions,
            max_items=max_items,
        )

    def botbr_get_favorite_entries(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[Entry]:
        """
        List all entries favorited by the BotBr with the given ID.

        :param botbr_id: ID of the BotBr to get favorites for.
        :param desc: If True, returns items in descending order. Requires sort key to be
            set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value as
            the value. Note that filters are deprecated; conditions should be used
            instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: List of Entry objects representing the list results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _conditions = [Condition("id", "IN_SUBQUERY:botbr_favorites", botbr_id)]
        if conditions:
            _conditions = conditions | _conditions

        return self.entry_list(
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=_conditions,
            max_items=max_items,
            offset=offset,
        )

    def botbr_get_palettes(
        self,
        botbr_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[Palette]:
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
        :param offset: Skip the first N items.
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

    def botbr_get_badge_progress(self, botbr_id: int) -> Dict[str, int]:
        """
        Get the badge progress for the BotBr with the given ID.

        This is the same as the list in the Badges tab of a BotBr's profile; if you're
        only interested in which badges a BotBr has earned and which level they're at,
        use the regular BotBr load/list/etc. endpoints - this information is returned by
        the API.

        **This is an unofficial method**; it uses parsed data from the site, not an API
        endpoint.

        :param botbr_id: ID of the BotBr to get badge progress for.
        :returns: Dictionary with badge token as the key and progress as the value. Dict
            will be empty if the BotBr was not found.
        :raises ConnectionError: On connection error.
        """
        out = {}

        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxBadges/{botbr_id}"
        )
        if ret.status_code == 500 and not ret.text:
            # Not found
            return out

        soup = BeautifulSoup(ret.text, "lxml")

        # .grid_4 > .inner:
        #   - div.t0.fright (progress / next threshold) \t (percentage)
        #   - div.botb-icon (icon)
        #   - span.tb1 (format name)
        for entry in soup.html.body.find_all("div", "grid_4"):
            inner = list(entry.contents)[1]
            format = inner.find_all("span", "tb1")[0].text.strip()
            progress = int(inner.find_all("div", "t0")[0].text.split("/")[0].strip())
            out[format] = progress

        return out

    def botbr_get_tags_given(self, botbr_id: int) -> List[str]:
        """
        List tags given by the BotBr.

        This is the same as the list in the Tags tab of a BotBr's profile.

        **This is an unofficial method**; it uses parsed data from the site, not an API
        endpoint.

        :param botbr_id: ID of the BotBr to get given tags for.
        :returns: List of given tags. List will be empty if the BotBr was not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxTag/{botbr_id}"
        )
        if ret.status_code == 500 and not ret.text:
            # Not found
            return []

        soup = BeautifulSoup(ret.text, "lxml")

        # First <p> element is Tags Given
        return list(parse_tag_cloud(soup.find_all("p")[0].prettify()).keys())

    def botbr_get_tags_received(self, botbr_id: int) -> List[str]:
        """
        List tags received by the BotBr.

        This is the same as the list in the Tags tab of a BotBr's profile.

        **This is an unofficial method**; it uses parsed data from the site, not an API
        endpoint.

        :param botbr_id: ID of the BotBr to get received tags for.
        :returns: List of given tags. List will be empty if the BotBr was not found.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxTag/{botbr_id}"
        )
        if ret.status_code == 500 and not ret.text:
            # Not found
            return []

        soup = BeautifulSoup(ret.text, "lxml")

        # Second <p> element is Tags Received
        return list(parse_tag_cloud(soup.find_all("p")[1].prettify()).keys())

    def botbr_get_avatars(self, botbr_id: int) -> List[str]:
        """
        List the URLs of the current and all past avatars of the BotBr.

        This is the same as the list in the Avatars tab of a BotBr's profile.

        **This is an unofficial method**; it uses parsed data from the site, not an API
        endpoint.

        :param botbr_id: ID of the BotBr to get avatars for.
        :returns: List of avatar URLs. List will be empty if the BotBr was not found or
            had no avatars or has avatar history disabled.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxAvatars/{botbr_id}"
        )
        if ret.status_code == 500 and not ret.text:
            # Not found
            return []

        soup = BeautifulSoup(ret.text, "lxml")

        return [
            "https://battleofthebits.com" + img["src"] for img in soup.find_all("img")
        ]

    def botbr_get_battles_hosted(
        self,
        botbr_id: int,
        submitted_only: bool = False,
        desc: bool = True,
        sort: Optional[str] = "id",
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[Battle]:
        """
        Get a list of battles hosted by the BotBr with the given ID.

        This is the same as the list in the Battles Hosted tab of a BotBr's profile
        (so, it includes battles both directly hosted *and* co-hosted by the BotBr).

        **This is an unofficial method**; it uses parsed data from the site,
        not an API endpoint. A similar endpoint could be implemented with just
        API methods; in which case, one would have to combine the following queries:

        - "botbr_id" matches the ID of the botbr;
        - If there's a + sign in "hosts_names" (and the BotBr hosting the battle doesn't simply
          have a + in their username), it's a cohosted battle.
          Names are joined by + signs; you'll likely need to perform three "hosts_names LIKE"
          conditions to get them correctly: "{name} +%", "%+ {name} +%" and "%+ {name}".

        Since this is a lot of work and cannot be easily combined into one iterable
        (not with our tools, anyways! Maybe in the future...), we just parse the site
        instead.

        :param botbr_id: ID of the BotBr to get avatars for.
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: `PaginatedList` of battles that the BotBr hosted/co-hosted.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxHosted/{botbr_id}"
        )

        if ret.status_code == 500 and not ret.text:
            # Not found
            return []

        soup = BeautifulSoup(ret.text, "lxml")
        battle_ids = []

        i = 0
        for battle_a in soup.find_all("a"):
            battle_url = battle_a["href"]
            if not battle_url:
                continue

            battle_id = int(
                battle_url.split("https://battleofthebits.com/arena/Battle/")[1].split(
                    "/"
                )[0]
            )
            battle_ids.append(battle_id)

            i += 1
            if (
                max_items > 0
                and i > max_items
                and sort == "id"
                and desc is True
                and not filters
                and not conditions
                and not offset
            ):
                break

        _conditions = [Condition("id", "IN", battle_ids)]
        if conditions:
            _conditions = conditions | _conditions

        return self.battle_list(
            sort=sort,
            desc=desc,
            filters=filters,
            conditions=_conditions,
            max_items=max_items,
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[Battle]:
        """
        Search for battles that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Battle`.

        :api: /api/v1/battle/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Battle objects representing the search results.
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
            offset=offset,
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
        :returns: List of Battle objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "battle", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Battle.from_payload(payload))

        return out

    def battle_search(
        self, query: str, max_items: int = 0, offset: int = 0
    ) -> Iterable[Battle]:
        """
        Search for battles that match the given query.

        :api: /api/v1/battle/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Battle objects representing the search results. If
            the search returned no results, the resulting iterable will return no
            results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._battle_search_noiter, query=query, max_items=max_items, offset=offset
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

    def battle_list_by_date(self, date: Union[str, dt_date, datetime]) -> List[Battle]:
        """
        List all battles that happened/were ongoing on this year-month-day date (EST
        timezone).

        :api: /api/v1/battle/list_by_date
        :param date: Date to look for; either a string in "YYYY-MM-DD" format
            or a :class:`datetime.date` or :class:`datetime.datetime` object.
        :returns: List of Battle objects representing the battles. If there are no
            matching battles, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        _valueerror_message = (
            'Param "date" must be a string in YYYY-MM-DD format or a datetime object'
        )

        # If the date is a string, convert it to a date object for validation.
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError(_valueerror_message) from e

        # This is NOT an elif - we override date strings with a date object just above.
        if isinstance(date, datetime) or isinstance(date, dt_date):
            date_str = date.strftime("%Y-%m-%d")
        else:
            raise ValueError(_valueerror_message)

        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/battle/list_by_date/{date_str}"
        )
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

    def battle_list_by_month(self, date: str = "") -> List[Battle]:
        """
        List all battles that happened/were ongoing on the specified month in the
        specified year (EST timezone).

        :api: /api/v1/battle/list_by_month
        :param date: Date as a YYYY-MM string.
        :param year: Year to look for.
        :param month: Month to look for.
        :returns: List of Battle objects representing the battles. If there are no
            matching battles, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/battle/list_by_month/{date}"
        )
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
        offset: int = 0,
    ) -> Iterable[Entry]:
        """
        Search for entries that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Entry`.

        :api: /api/v1/entry/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Entry objects representing the search results.
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
            offset=offset,
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
        :returns: List of Entry objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "entry", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Entry.from_payload(payload))

        return out

    def entry_search(
        self, query: str, max_items: int = 0, offset: int = 0
    ) -> Iterable[Entry]:
        """
        Search for entries that match the given query.

        :api: /api/v1/entry/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Entry objects representing the search results. If the
            search returned no results, the resulting iterable will return no results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._entry_search_noiter, query=query, max_items=max_items, offset=offset
        )

    def entry_get_tags(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
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
        :param offset: Skip the first N items.
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
            offset=offset,
        )

    def entry_get_playlist_ids(
        self, entry_id: int, max_items: int = 0, offset: int = 0
    ) -> List[int]:
        """
        Get a list containing the playlist IDs of playlists that this entry has been
        added to.

        To get a list of Playlist objects, see `:method:.BotBr.entry_get_playlists`.

        :param entry_id: ID of the entry to load the playlists of.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :param offset: Skip the first N items.
        :returns: List of playlist IDs.
        :raises ConnectionError: On connection error.
        """
        ret = PaginatedList(
            self._playlist_to_entry_list_noiter,
            filters={"entry_id": entry_id},
            max_items=max_items,
            offset=offset,
        )
        if not ret:
            return []

        return [p.playlist_id for p in ret]

    def entry_get_playlists(
        self,
        entry_id: int,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[Playlist]:
        """
        Get a list of playlists that this entry has been added to.

        :param entry_id: ID of the playlist to load the entries of.
        :param max_items: Maximum number of items to return; set to 0 for no limit.
        :param offset: Skip the first N items.
        :returns: List of Playlist objects.
        :raises ConnectionError: On connection error.
        """
        playlist_ids = self.entry_get_playlist_ids(entry_id, max_items=max_items)

        condition = Condition("id", "IN", playlist_ids)

        return self.playlist_list(
            sort="id", conditions=[condition], max_items=max_items, offset=offset
        )

    def entry_get_favorites(
        self,
        entry_id: int,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
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
        :param offset: Skip the first N items.
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
        offset: int = 0,
    ) -> Iterable[Favorite]:
        """
        Search for favorites that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Favorite`.

        :api: /api/v1/favorite/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Favorite objects representing the search results.
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
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[Format]:
        """
        Search for formats that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Format`.

        :api: /api/v1/format/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Format objects representing the search results.
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
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[GroupThread]:
        """
        Search for group threads that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.GroupThread`.

        :api: /api/v1/group_thread/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of GroupThread objects representing the search results.
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
            offset=offset,
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
        :returns: List of GroupThread objects representing the search results. If the
            search returned no results, the list will be empty.
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
        self, query: str, max_items: int = 0, offset: int = 0
    ) -> Iterable[GroupThread]:
        """
        Search for group threads that match the given query.

        :api: /api/v1/group_thread/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of GroupThread objects representing the search results.
            If the search returned no results, the resulting iterable will return no
            results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._group_thread_search_noiter,
            query=query,
            max_items=max_items,
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[LyceumArticle]:
        """
        Search for lyceum articles that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.LyceumArticle`.

        :api: /api/v1/lyceum_article/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of LyceumArticle objects representing the search results.
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
            offset=offset,
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
        :returns: List of LyceumArticle objects representing the search results. If the
            search returned no results, the list will be empty.
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
        self,
        query: str,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[LyceumArticle]:
        """
        Search for lyceum articles that match the given query.

        :api: /api/v1/lyceum_article/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of LyceumArticle objects representing the search
            results. If the search returned no results, the resulting iterable will
            return no results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._lyceum_article_search_noiter,
            query=query,
            max_items=max_items,
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[Palette]:
        """
        Search for palettes that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Palette`.

        :api: /api/v1/palette/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Palette objects representing the search results.
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
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[Playlist]:
        """
        Search for playlists that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Playlist`.

        :api: /api/v1/playlist/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Playlist objects representing the search results.
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
            offset=offset,
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
        :returns: List of Playlist objects representing the search results. If the
            search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "playlist", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Playlist.from_payload(payload))

        return out

    def playlist_search(
        self, query: str, max_items: int = 0, offset: int = 0
    ) -> Iterable[Playlist]:
        """
        Search for playlists that match the given query.

        :api: /api/v1/playlist/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Playlist objects representing the search results. If
            the search returned no results, the resulting iterable will return no
            results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._playlist_search_noiter,
            query=query,
            max_items=max_items,
            offset=offset,
        )

    def _playlist_to_entry_list_noiter(
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

    def playlist_get_entry_ids(
        self, playlist_id: int, max_items: int = 0, offset: int = 0
    ) -> List[int]:
        """
        Get a list containing the entry IDs of the playlist with the given ID, in the
        order that they appear in the playlist.

        To get a list of entry objects, see `:method:.BotBr.playlist_get_entries`.

        :param playlist_id: ID of the playlist to load the entries of.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: List of entry IDs.
        :raises ConnectionError: On connection error.
        """
        ret = PaginatedList(
            self._playlist_to_entry_list_noiter,
            filters={"playlist_id": playlist_id},
            max_items=max_items,
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[Tag]:
        """
        Search for tags that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.Tag`.

        :api: /api/v1/tag/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Tag objects representing the search results.
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
            offset=offset,
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
        :returns: List of Tag objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        """
        ret = self._search(
            "tag", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append(Tag.from_payload(payload))

        return out

    def tag_search(
        self, query: str, max_items: int = 0, offset: int = 0
    ) -> Iterable[Tag]:
        """
        Search for tags that match the given query.

        :api: /api/v1/tag/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of Tag objects representing the search results. If the
            search returned no results, the resulting iterable will return no results.
        :raises ConnectionError: On connection error.
        """
        return PaginatedList(
            self._tag_search_noiter, query=query, max_items=max_items, offset=offset
        )

    def tag_cloud_by_substring_html(self, substring: str) -> str:
        """
        Get the HTML representation of a tag cloud for tags matching the substring.

        :method:`.tag_cloud_by_substring` parses the HTML data into a dict of
        tag: size pairs for convenience.

        :api: /api/v1/tag/cloud_by_substring
        :param substring: String to pass as the search substring.
        :returns: String containing the HTML representation of the tag cloud.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get(
            f"https://battleofthebits.com/api/v1/tag/cloud_by_substring/{substring}"
        )

        return ret.text

    def tag_cloud_by_substring(self, substring: str) -> Dict[str, int]:
        """
        Get a tag cloud by the given substring; returns a dict of tag: size pairs.

        :api: /api/v1/tag/cloud_by_substring
        :param substring: String to pass as the search substring.
        :returns: Dict with tag name as the key and size in pixels as the value.
        :raises ConnectionError: On connection error.
        """
        ret = self.tag_cloud_by_substring_html(substring)

        return parse_tag_cloud(ret)

    def tag_get_entry_ids(self, tag: str) -> List[int]:
        """
        Get a list of entry IDs which have this tag.

        :param tag: Tag to fetch entries for.
        :returns: `PaginatedList` of entries which have the given tag.
        :raises ConnectionError: On connection error.
        """
        return list(
            set(
                [
                    t.entry_id
                    for t in self.tag_list(
                        sort="id", conditions=[Condition("tag", "LIKE", tag)]
                    )
                ]
            )
        )

    def tag_get_entries(
        self,
        tag: str,
        desc: bool = True,
        sort: Optional[str] = "id",
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
        offset: int = 0,
    ) -> Iterable[Entry]:
        """
        Get a `PaginatedList` of entries which have this tag.

        :param tag: Tag to fetch entries for.
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: `PaginatedList` of entries which have the given tag.
        :raises ConnectionError: On connection error.
        """
        entry_ids = self.tag_get_entry_ids(tag)
        if not entry_ids:
            return []

        _conditions = [Condition("id", "IN", entry_ids)]
        if conditions:
            _conditions = conditions | _conditions

        return self.entry_list(
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=_conditions,
            max_items=max_items,
            offset=offset,
        )

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
        offset: int = 0,
    ) -> Iterable[BotBrStats]:
        """
        Search for BotBr stats that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.BotBrStats`.

        :api: /api/v1/botbr_stats/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of BotBrStats objects representing the search results.
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
            offset=offset,
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
        offset: int = 0,
    ) -> Iterable[DailyStats]:
        """
        Search for daily stats that match the given query.

        For a list of supported filter/condition properties, see :py:class:`.DailyStats`.

        :api: /api/v1/daily_stats/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :param offset: Skip the first N items.
        :returns: :class:`PaginatedList` of DailyStats objects representing the search results.
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
            offset=offset,
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

    #
    # Miscelaneous
    #

    def firki_interpret(self, firki: str) -> str:
        """
        Interpret a Firki markup string into HTML.

        :api: /api/v1/firki/interpret
        :param firki: Firki markup input string.
        :returns: String containing HTML output.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.post(
            "https://battleofthebits.com/api/v1/firki/interpret",
            data={"firki_string": firki},
        )
        if ret.status_code == 500:
            raise ConnectionError(ret.text)

        try:
            # HACK: Firki interpret API always ends the returned string with "</span>"
            # (no matching starting bracket). It is removed here for ease-of-use.
            return ret.json()[0][:-7]
        except Exception as e:
            raise ConnectionError(ret.text) from e

    def spriteshit_version(self) -> str:
        """
        Return the current version of the BotB spritesheet (affectionately named the
        spriteshit).

        This version string can be used to fetch the spriteshit PNG from BotB's
        assets (https://battleofthebits.com/styles/spriteshit/{version}.png).

        :api: /api/v1/spriteshit/version
        :returns: The API version.
        :raises ConnectionError: On connection error.
        """
        ret = self._s.get("https://battleofthebits.com/api/v1/spriteshit/version")
        if ret.status_code == 500:
            raise ConnectionError(ret.text)

        try:
            return ret.json()["spriteshit_version"]
        except Exception as e:
            raise ConnectionError(ret.text) from e
