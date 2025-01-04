# SPDX-License-Identifier: MIT
"""
Make sure that all objects don't break when being turned into a dataclass (i.e. we
accidentally made a property required that shouldn't be).

This test is very time-intensive!
"""

from pybotb.botb import BotB

b = BotB()
# favorite is notably missing, which is because we trust it to be true. not going to download 1,500,000 entries
# for this :p
# "battle", "botbr", "entry", "format", "group_thread", "lyceum_article", "playlist", "tag"
for object_type in ("palette",):
    print(f"Testing {object_type}...")
    list_func = getattr(b, object_type + "_list")
    b.list_iterate_over_pages(list_func, sort="id")

print("Completed succesfully!")
