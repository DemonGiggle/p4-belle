"""Shared Textual widgets for responsive p5 TUIs."""
from __future__ import annotations

from textual.widgets import ListItem, ListView


class FastListView(ListView):
    """ListView that keeps the highlighted row in view without deferred scrolling."""

    def watch_index(self, old_index: int | None, new_index: int | None) -> None:
        if self._is_valid_index(old_index):
            old_child = self._nodes[old_index]
            assert isinstance(old_child, ListItem)
            old_child.highlighted = False

        if (
            new_index is not None
            and self._is_valid_index(new_index)
            and not self._nodes[new_index].disabled
        ):
            new_child = self._nodes[new_index]
            assert isinstance(new_child, ListItem)
            new_child.highlighted = True
            self.post_message(self.Highlighted(self, new_child))

            if new_child.region:
                self.scroll_to_widget(new_child, animate=False, immediate=True)
            else:
                self.call_after_refresh(
                    self.scroll_to_widget,
                    new_child,
                    animate=False,
                    immediate=True,
                )
        else:
            self.post_message(self.Highlighted(self, None))
