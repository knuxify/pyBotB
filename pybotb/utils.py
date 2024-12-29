# SPDX-License-Identifier: MIT
import dataclasses
from enum import Enum
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import Any, Type, Optional
import time


#: Maximum number of retries before we give up.
MAX_RETRIES = 3

# https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
REQ_RETRIES = Retry(
    total=MAX_RETRIES,
    connect=MAX_RETRIES,
    read=MAX_RETRIES,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
)


class Session(requests.Session):
    """Subclass of requests.Session with better retry handling and user agent field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mount("http://", HTTPAdapter(max_retries=REQ_RETRIES))
        self.mount("https://", HTTPAdapter(max_retries=REQ_RETRIES))
        self.set_user_agent("pybotb v{VERSION}")

    def get(self, url: str, retry_count: int = 0, **kwargs):
        """Wrapper for self._s.get with better retry handling."""
        if retry_count > MAX_RETRIES:
            raise ConnectionError("Maximum retries reached")

        try:
            ret = super().get(url, **kwargs)
        except:
            if (retry_count + 1) > MAX_RETRIES:
                raise ConnectionError("Maximum retries reached")

            time.sleep(3)

            return self.get(url, retry_count + 1, **kwargs)
        return ret

    def set_user_agent(self, user_agent: str):
        """Set the User-Agent header to a specific string."""
        headers = requests.utils.default_headers()
        headers.update({"User-Agent": user_agent})


def unroll_payload(
    cls: Type[Any], payload: dict, payload_to_attr: Optional[dict] = None
) -> Any:
    """
    Perform type casts for values in the payload to match the attributes of the provided
    dataclass.

    :param cls: Dataclass that will be returned.
    :param payload: JSON payload as a dict.
    :param payload_to_attr: Dict of attributes to rename, where the key is
                            the name of the attribute in JSON, and the value
                            is the name of the target attribute in the class.
    :returns: Instance of `cls` filled with values from the payload.
    """
    payload_parsed = {}
    attr_types = dict([(field.name, field.type) for field in dataclasses.fields(cls)])

    for payload_attr in payload.keys():
        if payload_to_attr and payload_attr in payload_to_attr:
            class_attr = payload_to_attr[payload_attr]
        else:
            class_attr = payload_attr

        if class_attr not in attr_types:
            continue

        class_attr_type = attr_types[class_attr]

        # Some types can be converted manually; others should be converted
        # by the function callers before calling.
        if class_attr_type in (int, float, str) or issubclass(class_attr_type, Enum):
            payload_parsed[class_attr] = class_attr_type(payload[payload_attr])
        elif class_attr_type == bool:
            val = payload[payload_attr]
            if type(val) == bool:
                payload_parsed[class_attr] = val
            elif type(val) == str:
                payload_parsed[class_attr] = False if val.lower() == "false" else True
            else:
                payload_parsed[class_attr] = bool(val)
        else:
            payload_parsed[class_attr] = payload[payload_attr]

    return cls(**payload_parsed)
