# SPDX-License-Identifier: MIT
"""BotB userbot helper class for performing actions as a user."""

from bs4 import BeautifulSoup
from dataclasses import dataclass
from enum import Enum
import re
import pickle
import os.path
from typing import List, Optional, Union

from .utils import req_session


class AlertType(Enum):
    """Alert types supported by pyBotB."""

    ALL = -1
    OTHER = 0
    GOT_BOONS = 1


@dataclass
class Alert:
    """BotB alert base class."""

    #: Type of the alert, auto-assigned based on the message
    type: AlertType  # = AlertType.OTHER
    message: str
    link: str
    #: Arbitrary data for the alert. Differs based on alert type.
    data: Optional[dict] = None

    @classmethod
    def from_message(cls, message: str, link: str):
        msg_type = AlertType.OTHER
        data = None

        # Boons alert
        res = re.search(
            r"(?P<username>(.*)) gave you b(?P<boons>([0-9.]*))( and they said \"(?P<message>(.*))\")?",
            message,
        )
        if res:
            data = {
                "username": res.group("username"),
                "boons": float(res.group("boons")),
                "message": res.group("message") or "",
            }
            msg_type = AlertType.GOT_BOONS

        return Alert(type=msg_type, message=message, link=link, data=data)


class UnauthenticatedException(Exception):
    """Exception raised when trying to call an authenticated method without
    authentication."""


def require_auth(func):
    """Decorator for BotB class functions which require authentication."""

    def wrapper(self, *args, **kwargs):
        if self.botbr_id is None:
            raise UnauthenticatedException(
                "This method requires authentication; create BotB object with .login() or .use_cookie_file()"
            )

        return func(self, *args, **kwargs)

    return wrapper


class BotBUserBot(BotB):
    """
    Class representing a userbot.

    Inherits from BotBHacks; thus, all API queries that can be done in BotB or BotBHacks
    can also be done on this object.
    """

    botbr_id: int
    user_id: int

    def __init__(self):
        super().__init__()
        self._botb = BotB()
        self.botbr_id = None
        self.user_id = None

    def _post_login_init(self, cookie_file: str = "_cookies.pkl"):
        """
        Common init steps shared by both of the login functions.

        :param cookie_file: Path to the cookie file; see :py
        :param:`BotBUserBot.login:cookie_file`.
        """
        cookies = self._s.cookies.get_dict()

        self.botbr_id = int(cookies["botbr_id"])

        # Users are tied to individual logins; a BotBr is bound to a user.
        # Apparently at some point having multiple BotBrs per user was planned[1].
        # Nonetheless, the user ID is usually different from the BotBr ID.
        # All API queries use the BotBr ID.
        # [1] https://discord.com/channels/239104268794200064/239107754575265803/642535630810906635
        self.user_id = int(cookies["user_id"])

        _user = self.get_self_botbr()
        if not _user:
            raise UnauthenticatedException(
                f"Failed to log in: can't find user for BotBr ID ({self.botbr_id})"
            )
        self.username = _user.name

        with open(cookie_file, "wb") as f:
            pickle.dump(self._s.cookies, f)

        return self

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        cookie_file: str = "_cookies.pkl",
        force_fresh_login: bool = False,
    ):
        """Log into BotB and get the session cookie."""
        if not os.path.exists(cookie_file) or force_fresh_login:
            b = cls()

            login_post = b._s.post(
                "https://battleofthebits.com/barracks/Login/",
                data={"email": email, "password": password, "submitok": "LOGIN"},
            )

            if login_post.status_code != 200:
                raise UnauthenticatedException(
                    "Failed to log in; check email and password"
                )

            return b._post_login_init(cookie_file=cookie_file)

        return cls.use_cookie_file(cookie_file)

    @classmethod
    def use_cookie_file(cls, cookie_file: str = "_cookies.pkl"):
        """Log into BotB using a saved session cookie."""
        b = cls()
        b._s = req_session()

        with open(cookie_file, "rb") as f:
            b._s.cookies.update(pickle.load(f))

        return b._post_login_init(cookie_file=cookie_file)

    #
    # Private API/hack methods
    #

    @require_auth
    def get_self_botbr(self):
        """Get your own profile info."""
        return self._botb.get_botbr_by_id(self.botbr_id)

    @require_auth
    def get_alerts(
        self, filter_types: Union[AlertType, List[AlertType]] = AlertType.ALL
    ) -> List[Alert]:
        """Get the last 100 alerts for the user."""
        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxAlerts/{self.botbr_id}"
        )
        if not ret:
            return []
        out = []
        soup = BeautifulSoup(ret.text, SOUP_PARSER)

        if isinstance(filter_types, AlertType):
            filter_types = [filter_types]

        # > .grid_8 > div.inner.clearfix > a.boxLink
        for alert_html in soup.select("a.boxLink"):
            message = alert_html.text.split("\n\t")[-1]
            alert = Alert.from_message(
                link=alert_html["href"],
                message=message,
            )

            if filter_types == [AlertType.ALL] or alert.type in filter_types:
                out.append(alert)

        return out

    @require_auth
    def give_boons(
        self,
        username: str,
        amount: float,
        message: str = "",
        overflow_message: bool = False,
    ):
        """Send boons to the given user."""
        if not overflow_message and len(message) > 56:
            raise ValueError("Message must be 56 characters or shorter")

        ret = self._s.post(
            f"https://battleofthebits.com/barracks/Profile/{username}/GaveBoons",
            data={
                "amount": amount,
                "message": message,
                "giveboons": "Give b00ns",
            },
        )

        # TODO error handling
        # if ret.status_code != 200:
        # 	print("error?", ret.status_code)
