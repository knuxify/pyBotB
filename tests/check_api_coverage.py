# SPDX-License-Identifier: MIT
"""
Script that parses pyBotB docstrings and compares the supported endpoints
against the ones reported by the documentation index.
"""

import pybotb.botb
import requests
from typing import Optional
import re

#: Base URL of the API.
API_BASE = "/api/v1/"


def get_documentation_index() -> dict:
    """
    Get the BotB documentation index for further parsing.

    :returns: Dictionary containing the documentation index.
    :raises ConnectionError: On connection error.
    """
    try:
        ret = requests.get(
            "https://battleofthebits.com" + API_BASE + "documentation/index"
        )
    except Exception as e:
        raise ConnectionError from e

    if ret.status_code != 200:
        raise ConnectionError

    return ret.json()


def get_api_endpoint_from_docstring(docstring: str) -> Optional[str]:
    """
    Retrieve the API endpoint from the docstring.

    :param docstring: Docstring to parse.
    :returns: String containing the API endpoint, or None if the endpoint is
              not provided.
    """
    endpoint = None

    # Adding an endpoint to the docstring is done by adding the following:
    #
    #   :api: /api/v1/...
    #
    # to the docstring.
    for line in docstring.split("\n"):
        if line.strip().startswith(":api:"):
            endpoint = line.split(":api:")[1].strip()
            break

    return endpoint


#: Ignored endpoints, with reasons.
IGNORED_ENDPOINTS = [
    "/api/v1/alert/botbr_checked",  # Userbot-only
    "/api/v1/botbr_stats/load",  # Not useful; the ID of a botbr_stats object is not exposed
    # anywhere, so this API is unused.
    "/api/v1/botbr_stats/list",  # Returns 500 on all queries
    "/api/v1/playlist_to_entry/load",  # Not useful; the ID of a playlist_to_entry object
    # is not exposed anywhere, so this API is unused.
    "/api/v1/playlist_to_entry/random",  # Not useful; if you want a random playlist, use
    # /api/v1/playlist/random
    "/api/v1/documentation/index",  # Internal use only
    "/api/v1/group/post_show",  # Internal/admin endpoint
    "/api/v1/group/post_hide",  # Internal/admin endpoint
]

#: Ignored object type properties, with reasons.
IGNORED_PROPERTIES = {
    "BotBr": [
        "class",  # Renamed to botbr_class to avoid collision with Python class keyword
    ],
    "BotBrStats": [
        "date",
        "date_str",
    ],
    "DailyStats": [
        "date",
        "date_str",
    ],
    "Battle": [
        # Upstream:
        "profileURL",  # Redundant, see url
        "end",  # Renamed to end_str, end attr is a datetime object
        "end_date",  # Redundant
        "end_time_left",  # Redundant
        "period_end",  # Renamed to period_end_str, period_end attr is a datetime object
        "period_end_date",  # Redundant
        "period_end_seconds",  # Redundant
        "period_end_time_left",  # Redundant
        "start",  # Renamed to start_str
        "disable_penalty",  # Listed in the docs, but not actually returned by the API
        #: pyBotB overrides:
        "end_str",
        "start_str",
        "period_end_str",
    ],
    "Entry": [
        # Upstream:
        "datetime",  # Renamed to datetime_str, datetime is a datetime object
        "medium_audio",  # Collapsed into medium attr
        "medium_visual",  # Collapsed into medium attr
        "medium_other",  # Collapsed into medium attr
        # These are added into the API query result, but not listed as properties
        # in the documentation:
        "battle",
        "botbr",
        "format",
        # pyBotB overrides:
        "datetime_str",
        "medium",
    ],
    "GroupThread": [
        # Upstream:
        "first_post_timestamp",  # Renamed to first_post_timestamp_str, first_post_timestamp is a datetime object
        "last_post_timestamp",  # Renamed to last_post_timestamp_str, last_post_timestamp is a datetime object
        # pyBotB overrides:
        "first_post_timestamp_str",
        "last_post_timestamp_str",
    ],
    "Playlist": [
        # Upstream:
        "date_create",  # Renamed to date_create_str, date_create is a datetime object
        "date_modify",  # Renamed to date_modify_str, date_modify is a datetime object
        # pyBotB overrides:
        "date_create_str",
        "date_modify_str",
    ],
}


def dataclass_name_to_object_type(dataclass_name: str):
    """
    Convert a name from PascalCase (class name) to snake_case (object type name).
    """
    # https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case#1176023
    return re.sub(r"(?<!^)(?=[A-Z])", "_", dataclass_name).lower()


if __name__ == "__main__":
    doc_index = get_documentation_index()

    # Get list of API endpoints
    endpoints = []
    for object_type, doc in doc_index.items():
        for command in doc.get("commands", []):
            endpoints.append(API_BASE + object_type + "/" + command)

    # Iterate over every function in BotB object and check endpoint completeness
    pybotb_endpoints = []
    for func_name in dir(pybotb.botb.BotB):
        if func_name.startswith("__"):
            continue
        func = getattr(pybotb.botb.BotB, func_name)
        try:
            endpoint = get_api_endpoint_from_docstring(func.__doc__)
        except AttributeError:
            continue
        if endpoint:
            pybotb_endpoints.append(endpoint)

    missing = 0
    for endpoint in endpoints:
        if endpoint not in pybotb_endpoints and endpoint not in IGNORED_ENDPOINTS:
            print(f"Missing endpoint: {endpoint}")
            missing += 1

    not_upstream = 0
    for endpoint in pybotb_endpoints:
        if endpoint not in endpoints:
            print(f"Endpoint not in upstream documentation: {endpoint}")
            not_upstream += 1

    # Iterate over every dataclass and check property completeness
    missing_props = 0
    missing_props_ignored = 0
    not_upstream_props = 0
    not_upstream_props_ignored = 0

    for dataclass_name in dir(pybotb.botb):
        dataclass_props = []
        object_type = dataclass_name_to_object_type(dataclass_name)
        if object_type not in doc_index:
            continue

        object_props = doc_index[object_type]["properties"]
        dataclass = getattr(pybotb.botb, dataclass_name)

        for prop in dataclass.__dataclass_fields__:
            if prop.startswith("_"):
                continue
            dataclass_props.append(prop)

        for prop in object_props:
            if prop in IGNORED_PROPERTIES.get(dataclass_name, []):
                missing_props_ignored += 1
                continue

            if prop not in dataclass_props:
                print(f"Missing property: {dataclass_name}.{prop}")
                missing_props += 1

        for prop in dataclass_props:
            if prop in IGNORED_PROPERTIES.get(dataclass_name, []):
                not_upstream_props_ignored += 1
                continue

            if prop not in object_props and prop not in IGNORED_PROPERTIES.get(
                dataclass_name, []
            ):
                print(
                    f"Property not in upstream documentation: {dataclass_name}.{prop}"
                )
                not_upstream_props += 1

    n_ignored = len(IGNORED_ENDPOINTS)
    n_endpoints = len(endpoints) - n_ignored
    present = n_endpoints - missing
    present_percent = (present / n_endpoints) * 100

    # Fancy colors, why not!
    if present_percent >= 100:
        col_present = "32"  # Green
    elif present_percent > 50:
        col_present = "33"  # Yellow/orange
    else:
        col_present = "31"  # Red

    if not_upstream > 0:
        col_not_upstream = "31"  # Red
    else:
        col_not_upstream = "32"  # Green

    if missing_props > 0:
        col_missing_props = "31"  # Red
    else:
        col_missing_props = "32"  # Green

    if not_upstream_props > 0:
        col_not_upstream_props = "31"  # Red
    else:
        col_not_upstream_props = "32"  # Green

    print("\n\033[1mSummary:\033[0m\n")
    print(
        f" - \033[{col_present};1m{present}/{n_endpoints}\033[0;{col_present}m ({present_percent:.02f}%) endpoint(s) implemented \033[3m({n_ignored}/{len(endpoints)} ignored)\033[0m"
    )
    print(
        f" - \033[{col_not_upstream};1m{not_upstream}\033[0;{col_not_upstream}m endpoint(s) not in upstream documentation\033[0m"
    )
    print(
        f" - \033[{col_missing_props};1m{missing_props}\033[0;{col_missing_props}m properties missing from dataclasses \033[3m({missing_props_ignored} ignored)\033[0m"
    )
    print(
        f" - \033[{col_not_upstream_props};1m{not_upstream_props}\033[0;{col_not_upstream_props}m properties not upstream from dataclasses \033[3m({not_upstream_props_ignored} ignored)\033[0m"
    )
    print()
