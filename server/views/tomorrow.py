from .simplified import SimplifiedPage


class TomorrowPage(SimplifiedPage):
    def __init__(
        self,
        width,
        height,
        inner_width=None,
        inner_height=None,
        inner_align_x="center",
        inner_align_y="center",
    ):
        super().__init__(
            width,
            height,
            inner_width,
            inner_height,
            inner_align_x,
            inner_align_y,
        )
        self.name = "tomorrow"

    def template(self, **kwargs):
        super().template(
            map_url=kwargs["map_url"],
            forecast=kwargs["tomorrow_forecast"],
        )

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="tomorrow.css")
