# SPDX-License-Identifier: MIT
"""Common utility functions used in pyBotB."""

import dataclasses
from enum import Enum, IntEnum
from functools import cached_property
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import Any, Optional, Union, cast
import time


#: Maximum number of retries before we give up.
MAX_RETRIES = 3

# https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
REQ_RETRIES = Retry(
    total=MAX_RETRIES,
    connect=MAX_RETRIES,
    read=MAX_RETRIES,
    backoff_factor=1,
    # We do not force retries for 500 errors since multiple
    # parts of the API return them for 404 errors.
    status_forcelist=[502, 503, 504],
)


class Session(requests.Session):
    """Subclass of requests.Session with better retry handling and user agent field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mount("http://", HTTPAdapter(max_retries=REQ_RETRIES))
        self.mount("https://", HTTPAdapter(max_retries=REQ_RETRIES))
        self.set_user_agent("pybotb {VERSION}")

    def get(  # type: ignore
        self,
        url: str,
        *args,
        handle_notfound: bool = False,
        retry_count: int = 0,
        **kwargs,
    ):
        """
        Get data from an URL.

        Wrapper for self._s.get with better retry handling.

        :param url: URL to access.
        :param handle_notfound: Hack to handle load API returning error 500 on 404.
        :param retry_count: Current retry count.
        """
        if retry_count > MAX_RETRIES:
            raise ConnectionError("Maximum retries reached")

        try:
            ret = super().get(url, *args, **kwargs)
            if ret.status_code == 500 and handle_notfound:
                json = ret.json()
                if "unfounded" in json["response_message"]:
                    ret.status_code = 404
        except Exception as e:
            if (retry_count + 1) > MAX_RETRIES:
                raise ConnectionError("Maximum retries reached") from e

            time.sleep(3)

            return self.get(url, retry_count + 1, **kwargs)
        return ret

    def set_user_agent(self, user_agent: str):
        """Set the User-Agent header to a specific string."""
        headers = requests.utils.default_headers()
        headers.update({"User-Agent": user_agent})


def payload_cast(in_value: Any, out_type: type) -> Any:
    """
    Perform a type cast from the input value to the target type.

    :param in_value: Value to convert.
    :param out_type: Desired output type.
    """
    # Some types can be converted manually; others should be converted
    # by the function callers before calling.
    try:
        is_intenum = issubclass(out_type, IntEnum)
    except TypeError:
        is_intenum = False

    try:
        is_enum = issubclass(out_type, Enum)
    except TypeError:
        is_enum = False

    is_dataclass_with_payload = dataclasses.is_dataclass(out_type)
    if is_dataclass_with_payload:
        is_dataclass_with_payload = hasattr(out_type, "from_payload")

    try:
        is_typing_list = out_type.__origin__ is list  # type: ignore
    except AttributeError:
        is_typing_list = False

    # typing.List type with inner object type defined; cast recursively
    if is_typing_list:
        out = []
        for i in in_value:
            out.append(payload_cast(i, out_type.__args__[0]))  # type: ignore
        return out

    # Data class with from_payload method
    elif is_dataclass_with_payload:
        return out_type.from_payload(in_value)  # type: ignore

    # Int, Float, String as well as non-IntEnum Enum types
    elif out_type in (int, float, str) or (is_enum and not is_intenum):
        return out_type(in_value)

    # IntEnum (same as above, but convert value to int first)
    elif is_intenum:
        return out_type(int(in_value))

    # Boolean
    elif out_type is bool:
        val = in_value
        if type(val) is bool:
            return val
        elif type(val) is str:
            return False if val.lower() == "false" else True
        else:
            return bool(val)

    # Unknown type, return as-is
    return in_value


def unroll_payload(
    cls: type, payload: dict, payload_to_attr: Optional[dict] = None
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
    attr_types = dict(
        [(field.name, cast(type, field.type)) for field in dataclasses.fields(cls)]
    )

    for payload_attr in payload.keys():
        if payload_to_attr and payload_attr in payload_to_attr:
            class_attr = payload_to_attr[payload_attr]
        else:
            class_attr = payload_attr

        if class_attr not in attr_types:
            continue

        class_attr_type = attr_types[class_attr]

        try:
            payload_parsed[class_attr] = payload_cast(
                payload[payload_attr], class_attr_type
            )
        except Exception as e:
            raise ValueError(
                f"Failed to convert value of {class_attr} (object ID: {payload.get('id', None)}). This is a pyBotB bug!",
                e,
            ) from e

    try:
        return cls(**payload_parsed)
    except TypeError as e:
        raise TypeError(
            f"Payload missing required property {e}. This is a pyBotB bug! {payload_parsed}"
        ) from e


_NOT_FOUND = object()
_NOT_INITIALIZED = object()


class cached_property_dep(cached_property):
    """
    Decorator inspired by cached_property which automatically invalidates the property
    when an attribute with the given name changes.

    Inheriting from cached_property is done here solely to allow tools to interpret this
    as a cached property; we override its functions here.
    """

    def __init__(self, attr: str = ""):
        self.attrname = None
        self._attr_cached = _NOT_INITIALIZED

        self.dep_attrname = attr
        self._dep_attr_cached = _NOT_INITIALIZED

    def __call__(self, func):  # noqa: D102
        self.func = func
        self.__doc__ = func.__doc__
        self.__module__ = func.__module__
        return self

    def __set_name__(self, owner, name):
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property_dep instance without calling __set_name__ on it."
            )

        invalid = False

        # Check if the dependent value changed since we last checked it
        dep_attr_current = getattr(instance, self.dep_attrname)

        if dep_attr_current is not self._dep_attr_cached:
            del self._dep_attr_cached
            self._dep_attr_cached = dep_attr_current
            invalid = True

        val = self._attr_cached

        if invalid or val is _NOT_FOUND:
            val = self.func(instance)
            del self._attr_cached
            self._attr_cached = val

        return val


def param_stringify(to_stringify: Union[int, str, bool]):
    """
    Take a parameter and stringifies it to a json-like format suitable for dumping
    into urlencode (i.e. no quotes around strings).
    """
    if type(to_stringify) is bool:
        return "true" if to_stringify is True else "false"
    return str(to_stringify)
