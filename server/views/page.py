import os
import logging
from time import sleep
from PIL import Image
from airium import Airium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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

        os.makedirs(os.path.dirname(html_fp), exist_ok=True)
        with open(html_fp, "wb") as f:
            f.write(bytes(self.airium))
            f.close()

        driver = self._get_chromedriver()
        driver.get("file://" + html_fp)
        # Wait until window.onload has fired (rough.js drawn) or up to 10s
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
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
        # Required in containers: Chromium can't set up its sandbox without
        # extra kernel capabilities, and /dev/shm defaults to 64MB which it
        # exhausts immediately (manifests as "DevToolsActivePort doesn't exist").
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")

        # In Docker we have apt-installed chromium + matching chromium-driver.
        # Selenium 4.10+'s Selenium Manager only auto-discovers google-chrome,
        # so we point at the binary explicitly via binary_location and pass an
        # explicit Service for the system driver. Outside Docker (no system
        # driver), fall through to Selenium Manager's bootstrap.
        opts.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
        if os.path.exists("/usr/bin/chromedriver"):
            driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)
        else:
            driver = webdriver.Chrome(options=opts)

        driver.set_window_rect(width=self.image_width, height=self.image_height)
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "mobile": False,
                "width": self.image_width,
                "height": self.image_height,
                "deviceScaleFactor": 1,
            },
        )

        return driver
