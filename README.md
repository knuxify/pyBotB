# pyBotB

Python library for interacting with Battle of the Bits, both with the official API and with the site itself

**Extremely WIP!** This is the continuation of the BotB API library I made for [BoonGamble](https://github.com/knuxify/BoonGamble), with the hope of eventually using it for some new projects (wink wink nudge nudge). The code is pretty well documented, and there Will Be Docs, so hopefully this can serve some use to pyBotB library users *and* folks wanting to write their own BotB API libraries in other languages.

## Usage

Proper docs will appear soon. For now, here's the basics:

* API object is in `pybotb.botb.BotB`; you create this once and do all subsequent calls on it
* Userbot API object is in `pybotb.userbot.BotBUser`; it inherits from `BotB`, so you can do all the same calls on it. Currently somewhat useless and completely untested (this is code ripped out from BoonGamble).

For more explanations, see the code comments.
