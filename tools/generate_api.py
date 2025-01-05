# SPDX-License-Identifier: MIT
"""Auto-generate API methods for the given object types."""

import requests


def get_documentation_index() -> dict:
    """
    Get the BotB documentation index for further parsing.

    :returns: Dictionary containing the documentation index.
    :raises ConnectionError: On connection error.
    """
    try:
        ret = requests.get(
            "https://battleofthebits.com/api/v1/documentation/index"
        )
    except Exception as e:
        raise ConnectionError from e

    if ret.status_code != 200:
        raise ConnectionError

    return ret.json()


OBJECT_TYPES = [
    {"name": "BotBr", "object_type": "botbr", "dataclass_name": "BotBr"},
    {"name": "battle", "object_type": "battle", "dataclass_name": "Battle"},
    {"name": "entry", "object_type": "entry", "dataclass_name": "Entry"},
    {"name": "favorite", "object_type": "favorite", "dataclass_name": "Favorite"},
    {"name": "format", "object_type": "format", "dataclass_name": "Format"},
    {"name": "group thread", "object_type": "group_thread", "dataclass_name": "GroupThread"},
    {"name": "lyceum article", "object_type": "lyceum_article", "dataclass_name": "LyceumArticle"},
    {"name": "palette", "object_type": "palette", "dataclass_name": "Palette"},
    {"name": "playlist", "object_type": "playlist", "dataclass_name": "Playlist"},
    {"name": "tag", "object_type": "tag", "dataclass_name": "Tag"},
    {"name": "BotBr stat", "object_type": "botbr_stats", "dataclass_name": "BotBrStats"},
    {"name": "daily stat", "object_type": "daily_stats", "dataclass_name": "DailyStats"},
]

TEMPLATE_LOAD = """
    def {object_type}_load(self, {object_type}_id: int) -> Union[{dataclass_name}, None]:
        \"\"\"
        Load a {name}'s info by their ID.

        :api: /api/v1/{object_type}/load
        :param {object_type}_id: ID of the {object_type} to load.
        :returns: {dataclass_name} object representing the user, or None if the user is not found.
        :raises ConnectionError: On connection error.
        \"\"\"
        ret = self._load("{object_type}", {object_type}_id)
        if ret is None:
            return None

        return {dataclass_name}.from_payload(ret)"""

TEMPLATE_LIST = """
    def _{object_type}_list_noiter(
        self,
        page_number: int = 0,
        page_length: int = 25,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> List[{dataclass_name}]:
        \"\"\"
        Search for {name}s that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.{dataclass_name}`.

        :api: /api/v1/{object_type}/list
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :returns: List of {dataclass_name} objects representing the search results. If the
                  search returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        \"\"\"
        ret = self._list(
            "{object_type}",
            page_number=page_number,
            page_length=page_length,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
        )

        out = []
        for payload in ret:
            out.append({dataclass_name}.from_payload(payload))

        return out

    def {object_type}_list(
        self,
        desc: bool = False,
        sort: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
        max_items: int = 0,
    ) -> Iterable[{dataclass_name}]:
        \"\"\"
        Search for {name}s that match the given query (Non-PaginatedList version).

        For a list of supported filter/condition properties, see :py:class:`.{dataclass_name}`.

        :api: /api/v1/{object_type}/list
        :param desc: If True, returns items in descending order. Requires sort key to be set.
        :param sort: Object property to sort by.
        :param filters: Dictionary with object property as the key and filter value
                        as the value. Note that filters are deprecated; conditions
                        should be used instead.
        :param conditions: List of Condition objects containing list conditions.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: PaginatedList of {dataclass_name} objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        :raises ValueError: If a provided parameter is incorrect.
        \"\"\"
        return PaginatedList(
            self._{object_type}_list_noiter,
            desc=desc,
            sort=sort,
            filters=filters,
            conditions=conditions,
            max_items=max_items
        )"""

TEMPLATE_RANDOM = """
    def {object_type}_random(self) -> {dataclass_name}:
        \"\"\"
        Get a random {name}.

        :api: /api/v1/{object_type}/random
        :returns: {dataclass_name} object representing the user.
        :raises ConnectionError: On connection error.
        \"\"\"
        ret = self._random("{object_type}")

        return {dataclass_name}.from_payload(ret)"""

TEMPLATE_SEARCH = """
    def _{object_type}_search_noiter(
        self, query: str, page_number: int = 0, page_length: int = 25
    ) -> List[{dataclass_name}]:
        \"\"\"
        Search for {name}s that match the given query.

        :api: /api/v1/{object_type}/search
        :param query: Search query for the search.
        :param page_number: Number of the list page, for pagination.
        :param page_length: Length of the list page, for pagination (max. 250).
        :returns: PaginatedList of {dataclass_name} objects representing the search results.
                  If the search returned no results, the resulting iterable will return no
                  results.
        :raises ConnectionError: On connection error.
        \"\"\"
        ret = self._search(
            "{object_type}", query, page_number=page_number, page_length=page_length
        )

        out = []
        for payload in ret:
            out.append({dataclass_name}.from_payload(payload))

        return out

    def {object_type}_search(self, query: str, max_items: int = 0) -> Iterable[{dataclass_name}]:
        \"\"\"
        Search for {name}s that match the given query.

        :api: /api/v1/{object_type}/search
        :param query: Search query for the search.
        :param max_items: Maximum amount of items to return; 0 for no limit.
        :returns: List of {dataclass_name} objects representing the search results. If the search
            returned no results, the list will be empty.
        :raises ConnectionError: On connection error.
        \"\"\"
        return PaginatedList(self._{object_type}_search_noiter, query=query, max_items=max_items)
"""


def fill_template(template: str, obj: dict):
    """Fill template with object data."""
    return template.replace("{object_type}", obj["object_type"]).replace("{name}", obj["name"]).replace("{dataclass_name}", obj["dataclass_name"])


if __name__ == "__main__":
    doc = get_documentation_index()

    for obj in OBJECT_TYPES:
        print(f"""
    #
    # {obj["name"].capitalize().replace("Botbr", "BotBr")}s
    #""")
        if "load" in doc[obj["object_type"]]["commands"] and obj["object_type"] not in ["botbr_stats"]:
            print(fill_template(TEMPLATE_LOAD, obj))
        if "list" in doc[obj["object_type"]]["commands"]:
            print(fill_template(TEMPLATE_LIST, obj))
        if "random" in doc[obj["object_type"]]["commands"]:
            print(fill_template(TEMPLATE_RANDOM, obj))
        if "search" in doc[obj["object_type"]]["commands"]:
            print(fill_template(TEMPLATE_SEARCH, obj))
