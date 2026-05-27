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
        inner_width=None,
        inner_height=None,
        inner_align_x="center",
        inner_align_y="center",
    ):
        self.name = name
        self.image_width = width
        self.image_height = height
        self.image_inner_width = inner_width if inner_width is not None else width
        self.image_inner_height = inner_height if inner_height is not None else height
        self.image_inner_align_x = inner_align_x
        self.image_inner_align_y = inner_align_y
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
        pal_img = Image.new("P", (1, 1))
        pal: list[int] = []
        for v in (0, 85, 170, 255):
            pal += [v, v, v]
        pal += [0] * (768 - len(pal))
        pal_img.putpalette(pal)
        img.convert("RGB").quantize(
            colors=4, palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG
        ).convert("L").save(png_fp, format="png", optimize=True)

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

    def layout_css_variables(self) -> str:
        slack_x = max(self.image_width - self.image_inner_width, 0)
        slack_y = max(self.image_height - self.image_inner_height, 0)
        inner_vw = self.image_inner_width / 100.0
        inner_vh = self.image_inner_height / 100.0

        if self.image_inner_align_x == "left":
            pad_left, pad_right = 0, slack_x
        elif self.image_inner_align_x == "right":
            pad_left, pad_right = slack_x, 0
        else:
            pad_left = slack_x / 2
            pad_right = slack_x - pad_left

        if self.image_inner_align_y == "top":
            pad_top, pad_bottom = 0, slack_y
        elif self.image_inner_align_y == "bottom":
            pad_top, pad_bottom = slack_y, 0
        else:
            pad_top = slack_y / 2
            pad_bottom = slack_y - pad_top

        return (
            f"--outer-width:{self.image_width}px;"
            f"--outer-height:{self.image_height}px;"
            f"--inner-width:{self.image_inner_width}px;"
            f"--inner-height:{self.image_inner_height}px;"
            f"--inner-vw:{inner_vw}px;"
            f"--inner-vh:{inner_vh}px;"
            f"--inner-pad-left:{pad_left}px;"
            f"--inner-pad-right:{pad_right}px;"
            f"--inner-pad-top:{pad_top}px;"
            f"--inner-pad-bottom:{pad_bottom}px;"
        )
