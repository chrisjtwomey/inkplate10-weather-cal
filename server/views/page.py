import os
import logging
from time import sleep
from PIL import Image
from airium import Airium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException


class Page:
    def __init__(
        self,
        name,
        width,
        height,
    ):
        self.name = name
        self.image_width = width
        self.image_height = height
        self.log = logging.getLogger(self.name)

        self.airium = Airium()     

    def template(self, **kwargs):
        raise NotImplementedError(
            "Page {} should implement function {}".format(
                self.__class__.__name__, self.template.__name__
            )
        )

    def save(self):
        cwd = os.path.dirname(os.path.realpath(__file__))
        html_fp = os.path.join(cwd, "html", self.name + ".html")
        png_fp = os.path.join(cwd, self.name + ".png")

        with open(html_fp, "wb") as f:
            f.write(bytes(self.airium))
            f.close()

        driver = self._get_chromedriver()
        driver.get("file://" + html_fp)
        sleep(1)
        driver.get_screenshot_as_file(png_fp)
        driver.quit()

        img = Image.open(png_fp)
        img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
        img.save(png_fp, format="png", optimize=True, quality=25)

        self.log.info("Screenshot captured and saved to file.")

    def _get_chromedriver(self):
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--hide-scrollbars")
        opts.add_argument("--window-size={},{}".format(self.image_width, self.image_height))
        opts.add_argument("--force-device-scale-factor=1")

        driver = None
        try:
            driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
        except Exception as e:
            self.log.warning(e)
            try:
                driver = webdriver.Chrome(options=opts)
            except WebDriverException as wde:
                raise wde 

        driver.set_window_rect(width=self.image_width, height=self.image_height)

        return driver
