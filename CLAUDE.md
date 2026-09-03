# Inkplate 10 Weather Calendar

**Read [CONTRIBUTING.md](CONTRIBUTING.md) first.** It covers the repository layout, how to run the tests, and how to build and run things locally.

## This repo

- A thin consumer of [epd](https://github.com/chrisjtwomey/epd). Firmware here is only `src/main.cpp` (board choice) and `src/defaults.cpp` (credentials); the rest is the `EpdClient` and `EpdBoardInkplate` libraries. The server is `server/server.py` (config keys, weather service, five pages, one `DisplayServer(...).run()`), the weather providers under `server/weather/`, and the views under `server/views/`.
- epd must be checked out beside this repo: `lib_deps` uses `symlink://../epd/firmware`. To develop against a local kit checkout, `pip install -e ../epd/server` in the server venv.
- Generic code does not belong here. If a change is not about weather, maps, or these five pages, it goes in epd with its tests, and this repo consumes it.
- Each view declares the datasets it needs in `Page.requires`; `WeatherService.datasets()` names what it provides. Keep the two in step — `tests/test_regenerate_pipeline.py` checks it.

## Sign every commit

The `main` branch rules require verified signatures. Git is configured to
GPG-sign commits and tags with key `2FAEAB8A2DB5FE61`. If a commit fails to
sign, fix the signing setup — do not commit unsigned.

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

## General rules when working in this codebase

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Goal-Driven Execution

**Define success criteria. Loop until verified. If tests exist, they must pass. If you weren't asked for tests, verify the code builds.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Code comments and documentation

### 1. Describe the present, not the change

Comments state how the code behaves now. They are not a changelog.

- No "changed to…", "now returns…", "previously…", "fixed so that…".
- No ticket or PR numbers standing in for an explanation.
- If a comment only makes sense to someone who saw the diff, cut it.

Git already holds the history, and a comment that narrates a change is stale the moment the next one lands.

### 2. Let the code carry the meaning

- Start a doc comment with a one-line summary of what the thing does.
- Inside a function body, reach for a better name, an extracted function, or a simpler conditional before reaching for a comment.
- If a body still seems to need one — a subtle contract, a load-bearing ordering, a trap the next reader will "tidy up" — ask before adding it.

Ask yourself: "Could I delete this comment by naming something better?" If yes, do that instead.

### 3. Say it once, and stop

- A sentence or two. A comment is not a design document.
- State what it does and what it hands back. Nothing more.
- Don't paraphrase the signature — the reader can see the parameters.
- Don't restate a system-wide idea in a low-level helper. Repeat an architectural rule everywhere and a reader starts hunting for the places it doesn't hold.

### 4. Assume competence

**Assume the reader has reasonable competence in the programming languages, principles, and practice.**

- Spend the words on what the code can't say: why this ordering, why this field is trusted without a guard, why this parse is a gate rather than a convenience.

The test: a comment that would read the same in any codebase isn't earning its place.

### 5. Plain language, not metaphor

**Name the thing itself — the function, the caller, the package, the type.**

- Borrowed imagery reads as precision but charges the reader a translation step.
- Tree and graph terms are the usual offenders: "low-level helper", not "leaf function"; "the packages that import it", not "its parents".
- Worse when the word is already taken — here "page" is a rendered image and "display" is the panel.

Ask yourself: "Does the metaphor explain this better than plain words would?" If you have to weigh it up, it doesn't.
