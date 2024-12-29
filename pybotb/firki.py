# SPDX-License-Identifier: MIT
"""Firki markup parser."""

from dataclasses import dataclass
from enum import Enum
from typing import Union


class FirkiExceptionType(Enum):
    OTHER = 0


class FirkiException(Exception):
    """Exception raised on Firki markup parsing errors."""

    def __init__(self, message: str, errno: FirkiExceptionType, *args):
        super().__init__(message, *args)
        self.errno = errno

    def __eq__(self, other):
        return self.errno == other.errno or super().__eq__(other)


@dataclass
class FirkiToken:
    """Firki markup token."""

    params: List[str] = []

    def __str__(self):
        out = "'[{self.action}"
        if self.params:
            for p in self.params:
                out += f"'[{p}"


class Firki:
    """
    Firki markup parser class.

    Acts like a string containing the markup but provides some common functions,
    e.g. for converting to other formats.

    It is also iterable - every item is returned as either a string (for plaintext)
    or FirkiToken.
    """

    def __init__(self, content: Union[str, list]):
        """Create Firki markup parser from text input."""
        self._markup = []

    @property
    def markup(self):
        """Returns a list of the full markup."""
        return self._markup

    @markup.setter
    def markup(self, value: list):
        """
        Set the inner markup list directly.

        If you want to create new markup from a string, either create a new object with
        Firki.from_str, or replace the markup of the current object with
        Firki.from_str_inplace.
        """
        pass  # TODO

    def __add__(self, new: Union[str, FirkiToken, Firki]):
        """Allows for either joining two Firkis together, or concatenating tokens."""
        if isinstance(new, str):
            if self._markup:
                return self._markup
            else:
                return self._markup + [new]

        elif isinstance(new, FirkiToken):
            pass  # TODO

    @classmethod
    def _from_str(cls):
        """Convert a string to a Firki markup object."""
        # TODO

    @classmethod
    def from_str(cls, input_str: str):
        """Create a new Firki markup object from the provided string."""
        firki = cls()
        firki.from_str_inplace(input_str)
        return firki
