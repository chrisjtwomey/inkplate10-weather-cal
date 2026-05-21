from .simplified import SimplifiedPage


class TomorrowPage(SimplifiedPage):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.name = "tomorrow"

    def template(self, **kwargs):
        super().template(
            map_url=kwargs["map_url"],
            forecast=kwargs["tomorrow_forecast"],
        )

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="tomorrow.css")
