# Project rules

## Verify image changes visually

When a change affects the rendered calendar images, do not stop at the tests.
Regenerate the images, check the generated HTML first, then inspect the PNGs.

1. Run the server once from the `server` directory:

   ```sh
   CHROME_BIN="/c/Program Files/Google/Chrome/Application/chrome.exe" ../.venv/Scripts/python.exe server.py --once
   ```

2. Check the generated HTML first — it is cheaper to read than the images.
   The renderer writes each page's HTML to `server/views/html/<page>.html`
   before it screenshots it. Grep or read the part the change affects — for
   example, the `<img src=...>` of a weather icon. If the HTML is wrong, fix
   it before rendering again.

3. When the HTML looks right, read the relevant PNGs in `server/views/`
   (`today.png`, `current.png`, `hourly.png`, `daily.png`, `tomorrow.png`)
   and confirm the change is visible and correct — for example, that an icon
   renders instead of a broken-image box.

This applies to the weather service parsers (icon selection, forecast data),
the page templates under `server/views/`, and anything else that alters what
the rendered images contain.
