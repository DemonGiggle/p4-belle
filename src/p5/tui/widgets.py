"""Shared Textual widgets for responsive p5 TUIs."""
from __future__ import annotations

from textual.actions import SkipAction
from textual.containers import ScrollableContainer
from textual.widgets import ListItem, ListView, RichLog


class _ImmediatePageScrollMixin:
    """Default page scrolling to an immediate jump instead of animation."""

    def scroll_page_down(
        self,
        *,
        animate: bool = False,
        speed: float | None = None,
        duration: float | None = None,
        easing=None,
        force: bool = False,
        on_complete=None,
        level: str = "basic",
    ) -> None:
        self.scroll_to(
            y=self.scroll_y + self.scrollable_content_region.height,
            animate=animate,
            speed=speed,
            duration=duration,
            easing=easing,
            force=force,
            on_complete=on_complete,
            level=level,
            immediate=not animate,
        )

    def scroll_page_up(
        self,
        *,
        animate: bool = False,
        speed: float | None = None,
        duration: float | None = None,
        easing=None,
        force: bool = False,
        on_complete=None,
        level: str = "basic",
    ) -> None:
        self.scroll_to(
            y=self.scroll_y - self.scrollable_content_region.height,
            animate=animate,
            speed=speed,
            duration=duration,
            easing=easing,
            force=force,
            on_complete=on_complete,
            level=level,
            immediate=not animate,
        )


class FastListView(_ImmediatePageScrollMixin, ListView):
    """ListView that keeps the highlighted row in view without deferred scrolling."""

    def action_page_down(self) -> None:
        if not self.allow_vertical_scroll:
            raise SkipAction()
        self.scroll_page_down()
        self._highlight_first_visible()

    def action_page_up(self) -> None:
        if not self.allow_vertical_scroll:
            raise SkipAction()
        self.scroll_page_up()
        self._highlight_first_visible()

    def _highlight_first_visible(self) -> None:
        viewport_height = self.scrollable_content_region.height
        if not viewport_height:
            self.call_after_refresh(self._highlight_first_visible)
            return

        top = self.scroll_y
        bottom = top + viewport_height
        for index, item in enumerate(self._nodes):
            if item.disabled:
                continue
            region = item.virtual_region
            if region.height and region.bottom > top and region.y < bottom:
                self.index = index
                return

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


class FastScrollableContainer(_ImmediatePageScrollMixin, ScrollableContainer):
    """Scrollable container with immediate page-up/page-down behavior."""


class FastRichLog(_ImmediatePageScrollMixin, RichLog):
    """RichLog with immediate page-up/page-down behavior."""
