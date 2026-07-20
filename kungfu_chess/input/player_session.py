"""Records which color each local player claimed first ("whichever color
a player clicks first becomes their color for that session" - see
UI_PLAN.md Sec 3). Bookkeeping only for now: with a single shared mouse
there's no way to tell which human made a given click, so nothing here
gates Controller's click handling yet. This exists so a future networked
phase, where each connection maps to its own PlayerSession, has
somewhere to plug in without redesigning Controller.
"""


class PlayerSession:
    def __init__(self):
        self._claimed_colors = []

    def claim(self, color):
        if color not in self._claimed_colors:
            self._claimed_colors.append(color)

    def claimed_colors(self):
        return list(self._claimed_colors)