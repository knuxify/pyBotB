# SPDX-License-Identifier: MIT
"""
Script that parses pyBotB docstrings and compares the supported endpoints
against the ones reported by the documentation index.
"""

import pybotb.botb
import requests
from typing import Optional

#: Base URL of the API.
API_BASE = "/api/v1/"

def get_documentation_index() -> dict:
    """
    Get the BotB documentation index for further parsing.

    :returns: Dictionary containing the documentation index.
    :raises pybotb.botb.ConnectionError: On connection error.
    """
    try:
        ret = requests.get("https://battleofthebits.com" + API_BASE + "documentation/index")
    except:
        raise pybotb.botb.ConnectionError

    if ret.status_code != 200:
        raise pybotb.botb.ConnectionError

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
    "/api/v1/alert/botbr_checked",       # Userbot-only
    "/api/v1/playlist_to_entry/load",    # Not useful; the ID of a playlist_to_entry object
                                         # is not exposed anywhere, so this API is unused.
    "/api/v1/playlist_to_entry/random",  # Not useful; if you want a random playlist, use
                                         # /api/v1/playlist/random
    "/api/v1/documentation/index",       # Internal use only
]

if __name__ == "__main__":
    # Get list of API endpoints
    endpoints = []
    for object_type, doc in get_documentation_index().items():
        for command in doc.get("commands", []):
            endpoints.append(API_BASE + object_type + "/" + command)

    # Iterate over every function in BotB object
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

    print("\n\033[1mSummary:\033[0m\n")
    print(f" - \033[{col_present};1m{present}/{n_endpoints}\033[0;{col_present}m ({present_percent:.02f}%) endpoint(s) implemented \033[3m({n_ignored} ignored)\033[0m")
    print(f" - \033[{col_not_upstream};1m{not_upstream}\033[0;{col_not_upstream}m endpoint(s) not in upstream documentation\033[0m")
    print()
