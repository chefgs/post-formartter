# Automated Unit Testing for a Browser-Based Unicode Text Formatter

## How I used Claude Code to add 144 Jest tests to a standalone HTML app, fix 9 bugs, and build a regression safety net — without touching the UI

---

## The Problem

The [Social Media Post Formatter](https://github.com/gsaravanan/post-formatter) is a single-page web application that converts plain text into stylized Unicode characters — bold, italic, fraktur, script, double-struck, and more — for use in LinkedIn posts, Twitter, and other social platforms.

The entire application was a single `html/index.html` file with inline JavaScript. No build system, no modules, no tests.

Over time, several bugs had crept in silently:

- The **Fraktur R** was rendering the same glyph as Fraktur S (a direct character duplication)
- The **Fraktur Z** was accidentally using the *lowercase* z fraktur character (𝔷) instead of the uppercase (ℨ)
- Three Fraktur letters (C, H, I) pointed to **unassigned Unicode codepoints** — rendering as empty boxes in some environments
- Eight Script uppercase letters were using **Mathematical Italic** characters instead of Mathematical Script characters
- The **italic serif** style was identical to **italic sans** — making the reverse lookup collide and format detection unreliable
- The **circular** style's uppercase letters from C onward used **Bold Fraktur** glyphs instead of the correct Double-Struck (𝕀𝕁𝕂…) glyphs
- The **clearFormat** function only stripped combining diacritics (underlines), never converting Unicode math characters back to ASCII — so bold text would remain bold after "clearing"
- The **toggle** logic failed for multi-word selections — "𝗛𝗲𝗹𝗹𝗼 𝗪𝗼𝗿𝗹𝗱" could never be toggled off because the space character (always plain) confused the uniformity check
- The **Copy button** was invisible on mobile viewports

None of these were caught by any test, because there were no tests.

The goal: **add a comprehensive automated test suite and fix all the bugs**, with the tests acting as both a bug-discovery tool and a regression safety net going forward.

I used **[Claude Code](https://claude.ai/claude-code)** — Anthropic's AI coding assistant — to drive the entire process: codebase analysis, bug identification, architectural decisions, test authoring, and fixes. The full test suite and all bug fixes were written in a single session.

---

## The Core Challenge: Testing DOM-Less Browser JavaScript

The formatter logic was written as inline `<script>` tags inside `index.html`. To test it in Node.js (where Jest runs), two things were needed:

1. **Extract the logic** into a separate `.js` file
2. **Make it importable** by both the browser (`<script src="">`) and Node.js (`require()`)

### The Architecture Decision: UMD Pattern

The solution was the **Universal Module Definition (UMD)** pattern — a wrapper that detects the environment and exports accordingly:

```javascript
// js/formatter.js
(function (root, factory) {
    if (typeof module !== 'undefined' && module.exports) {
        // Node.js (for Jest)
        module.exports = factory();
    } else {
        // Browser — attach to window
        const exports = factory();
        Object.assign(root, exports);
    }
}(typeof self !== 'undefined' ? self : this, function () {

    // --- All the pure logic goes here ---
    const maps = { ... };
    function toPlain(char) { ... }
    function detectFormats(char) { ... }
    function applyFormatToText(text, format) { ... }
    function clearFormatText(text) { ... }

    return {
        maps, reverseMaps, detectFormats, toPlain,
        formatSetToString, applyFormatToText, clearFormatText,
        buzzwordEmojiMap, shortcodeMap, autoEmojifyText, convertShortcodesText
    };
}));
```

**The key insight:** All of the interesting formatter logic is *pure functions* — they take text in and return text out. They don't touch the DOM. They don't need a browser. Extracting them to `js/formatter.js` required zero changes to the logic itself.

The HTML file was updated to `<script src="../js/formatter.js"></script>`, and the inline functions that previously duplicated this logic now call the shared module.

---

## The Test Stack

```
AI assistant: Claude Code (claude.ai/claude-code)
Runtime:      Node.js (via nvm)
Test runner:  Jest 29
Test file:    tests/formatter.test.js
Logic file:   js/formatter.js
```

**package.json:**

```json
{
  "name": "post-formatter",
  "version": "1.0.0",
  "description": "Social Media Unicode Text Formatter",
  "scripts": {
    "test": "jest --verbose",
    "test:coverage": "jest --verbose --coverage"
  },
  "devDependencies": {
    "jest": "^29.7.0"
  },
  "jest": {
    "testEnvironment": "node",
    "testMatch": ["**/tests/**/*.test.js"]
  }
}
```

**Running tests:**

```bash
nvm use node
npm install
npm test
```

**Result: 144 tests, 13 suites, all passing.**

---

## The 13 Test Suites — Strategy and Rationale

### Suite 1: Map Completeness

**What it tests:** Every formatting style must have entries for all 26 lowercase letters, all 26 uppercase letters, and (for relevant styles) all 10 digits.

**Why it matters:** A missing entry means that letter silently passes through unformatted — the user sees plain text mixed in with styled text, which looks broken.

```javascript
const STYLE_NAMES = [
    'boldSans', 'italicSans', 'boldItalicSans', 'boldSerif', 'boldItalicSerif',
    'italicSerif', 'fraktur', 'script', 'circular', 'square'
];

describe('Map Completeness', () => {
    for (const style of STYLE_NAMES) {
        test(`${style} has all 26 lowercase letters`, () => {
            for (const c of 'abcdefghijklmnopqrstuvwxyz'.split('')) {
                expect(maps[style]).toHaveProperty(c);
                expect(maps[style][c]).toBeTruthy();
            }
        });
    }

    test('boldSans has digits 0-9', () => {
        for (let d = 0; d <= 9; d++) {
            expect(maps.boldSans).toHaveProperty(String(d));
        }
    });
});
```

**Pattern:** Use `for...of` loops to generate parameterized tests dynamically. Adding a new style to `STYLE_NAMES` automatically adds it to all applicable suites.

---

### Suite 2: No Intra-Map Duplicates

**What it tests:** Within a single style's character map, every output character must be unique — no two input letters should map to the same Unicode glyph.

**Why it matters:** A duplicate means two input characters are indistinguishable after formatting. The reverse lookup (used for detection and toggling) would silently fail for one of them.

This is exactly the bug that affected Fraktur R — it was mapped to 𝔖, which was *also* the mapping for S. Clicking "Fraktur" on text containing R would produce S-looking characters.

```javascript
describe('No Intra-Map Duplicates', () => {
    for (const style of STYLE_NAMES) {
        test(`${style}: all output characters are unique`, () => {
            const seen = new Set();
            const duplicates = [];
            for (const [key, val] of Object.entries(maps[style])) {
                if (seen.has(val)) duplicates.push({ key, val });
                seen.add(val);
            }
            expect(duplicates).toEqual([]);
        });
    }
});
```

**Pattern:** Build a `Set` of seen values; any repeated value is a duplicate. Report all duplicates at once rather than failing on first, to make debugging efficient.

---

### Suite 3: No Cross-Map Collisions

**What it tests:** The output characters of two different styles must not overlap. If `italicSans['a']` and `italicSerif['a']` produce the same Unicode character, the reverse map cannot distinguish which style was applied.

**Why it matters:** This was the root cause of the `italicSerif` bug. The italicSerif map was accidentally populated with the same characters as italicSans. When you applied italicSerif, the reverse map would detect it as italicSans, making the toggle logic wrong.

```javascript
const STYLE_PAIRS_TO_CHECK = [
    ['boldSans',    'italicSans'],
    ['italicSans',  'italicSerif'],   // CRITICAL: was identical before the fix
    ['italicSerif', 'script'],        // script uppercase had used italic chars
    ['fraktur',     'circular'],      // circular uppercase had used bold-fraktur chars
    // ... more pairs ...
];

for (const [styleA, styleB] of STYLE_PAIRS_TO_CHECK) {
    test(`${styleA} and ${styleB} share no alpha characters`, () => {
        const valsA = new Set(ALL_ALPHA.map(c => maps[styleA][c]).filter(Boolean));
        const collisions = ALL_ALPHA
            .map(c => maps[styleB][c])
            .filter(v => v && valsA.has(v));
        expect(collisions).toEqual([]);
    });
}
```

**Pattern:** The pairs are carefully chosen to cover all the historically-known collision risks. The comments in the test code explain *why* each pair is critical.

---

### Suite 4: Specific Bug Regression Checks

**What it tests:** 24 explicit character-level assertions, one per known historical bug. Each test names the bug, the wrong character, and the correct character.

**Why it matters:** These are the "never again" tests. Once a specific character is confirmed correct, this suite will catch any future regression immediately.

```javascript
describe('Specific Bug Regression Checks', () => {
    test('fraktur R is ℜ (U+211C), not S duplicate 𝔖', () => {
        expect(maps.fraktur['R']).toBe('ℜ');
        expect(maps.fraktur['R']).not.toBe(maps.fraktur['S']);
    });

    test('fraktur Z is ℨ (U+2128), not lowercase z fraktur 𝔷', () => {
        expect(maps.fraktur['Z']).toBe('ℨ');
        expect(maps.fraktur['Z']).not.toBe(maps.fraktur['z']);
    });

    test('script L is ℒ (U+2112), not lowercase script 𝓁', () => {
        expect(maps.script['L']).toBe('ℒ');
        expect(maps.script['L']).not.toBe(maps.script['l']);
    });

    test('italicSerif and italicSans use completely different characters', () => {
        for (const c of ALL_ALPHA) {
            expect(maps.italicSerif[c]).not.toBe(maps.italicSans[c]);
        }
    });

    test('circular C is ℂ (double-struck), not Bold Fraktur 𝕮', () => {
        expect(maps.circular['C']).toBe('ℂ');
        expect(maps.circular['C']).not.toBe('𝕮');
    });
});
```

**Pattern:** Use both `.toBe()` (the correct value) and `.not.toBe()` (the wrong value) in the same test. This makes the test self-documenting about what the bug *was* and what it was changed *to*.

---

### Suite 5: Reverse Map Round-Trip

**What it tests:** For every formatting style and every letter, `toPlain(maps[style][letter])` must equal the original letter. This validates the entire reverse lookup system.

**Why it matters:** The reverse map is what makes format detection and toggling work. A broken reverse map means the app cannot detect what formatting has been applied, making toggle fail silently.

```javascript
describe('Reverse Map Round-Trip', () => {
    for (const style of STYLE_NAMES) {
        test(`${style}: toPlain reverses all alpha characters`, () => {
            for (const c of ALL_ALPHA) {
                const formatted = maps[style][c];
                expect(formatted).toBeTruthy();
                expect(toPlain(formatted)).toBe(c);
            }
        });
    }

    test('plain ASCII characters pass through toPlain unchanged', () => {
        for (const c of ALL_ALPHA) {
            expect(toPlain(c)).toBe(c);
        }
    });
});
```

**Pattern:** The round-trip test is the ultimate integration test for the map + reverse-map system. If any character is wrong in the map (pointing to an unassigned codepoint, or stealing another letter's glyph), this test catches it because `toPlain` won't be able to look it up.

---

### Suite 6: Format Detection

**What it tests:** The `detectFormats()` function, which analyzes a single Unicode character and returns a `Set` of the formatting styles it belongs to.

**Why it matters:** Detection drives the toggle: before applying a format, the app checks whether all selected characters are already in that format. If detection is wrong, toggling is wrong.

```javascript
describe('Format Detection', () => {
    test('plain ASCII returns empty Set', () => {
        expect(detectFormats('a').size).toBe(0);
    });

    for (const [style, expectedKey] of singleFormatStyles) {
        test(`${style} char detected as {${expectedKey}}`, () => {
            const fmtA = detectFormats(maps[style]['a']);
            expect(fmtA.has(expectedKey)).toBe(true);
        });
    }

    test('boldItalicSans char detected as {boldSans, italicSans}', () => {
        const fmts = detectFormats(maps.boldItalicSans['a']);
        expect(fmts.has('boldSans')).toBe(true);
        expect(fmts.has('italicSans')).toBe(true);
    });
});
```

**Note on boldItalicSans:** This style is not stored as a separate map — it is the *composition* of `boldSans` and `italicSans`. Characters in this style are detected as belonging to *both* parent styles simultaneously. This reflects the underlying Unicode block structure (Mathematical Sans-Serif Bold Italic).

---

### Suite 7: Apply Format — Basic Application

**What it tests:** End-to-end formatting of short strings, verifying the exact Unicode output for each style.

**Why it matters:** This is the core user-facing behavior. If `applyFormatToText('hello', 'boldSans')` doesn't return `'𝗵𝗲𝗹𝗹𝗼'`, something fundamental is broken.

```javascript
test('boldSans applied to plain text produces bold sans chars', () => {
    expect(applyFormatToText('hello', 'boldSans')).toBe('𝗵𝗲𝗹𝗹𝗼');
});

test('fraktur applied to plain text', () => {
    // H (uppercase) → ℌ; e,l,o (lowercase) → 𝔢,𝔩,𝔬
    expect(applyFormatToText('Hello', 'fraktur')).toBe('ℌ𝔢𝔩𝔩𝔬');
});

test('spaces pass through any format unchanged', () => {
    expect(applyFormatToText('a b', 'boldSans')).toBe('𝗮 𝗯');
});

test('boldSans formats digits', () => {
    expect(applyFormatToText('123', 'boldSans')).toBe('𝟭𝟮𝟯');
});
```

**Unicode caveat in test source files:** The test file itself contains Unicode characters like `𝗵𝗲𝗹𝗹𝗼` (Mathematical Sans-Serif Bold). These look unusual in source code, but Jest handles them correctly as UTF-8 string literals. The source file must be saved as UTF-8.

---

### Suite 8: Toggle Behavior

**What it tests:** Applying the same format twice should return the original plain text.

**The space-skipping fix:** The original `allHaveSameState` check considered every character in the selection, including spaces. A space is always "plain" — it has no Unicode formatting. So "𝗛𝗲𝗹𝗹𝗼 𝗪𝗼𝗿𝗹𝗱" would always be detected as "mixed" (some formatted, one space that is plain), preventing toggle from ever removing the format.

The fix: filter to only alphabetic characters when checking uniformity.

```javascript
test('toggle works for text with spaces (space-skipping fix)', () => {
    const bold = applyFormatToText('Hello World', 'boldSans');
    expect(bold).toBe('𝗛𝗲𝗹𝗹𝗼 𝗪𝗼𝗿𝗹𝗱');

    // Before the fix, this would apply bold again instead of removing it
    const toggled = applyFormatToText(bold, 'boldSans');
    expect(toggled).toBe('Hello World');
});
```

The suite also tests all 9 individual styles for toggle correctness, and mixed-case text:

```javascript
for (const style of toggleStyles) {
    test(`${style}: apply twice → returns plain text`, () => {
        const formatted = applyFormatToText('Hello', style);
        const toggled = applyFormatToText(formatted, style);
        expect(toggled).toBe('Hello');
    });
}
```

---

### Suite 9: Format Composition

**What it tests:** Layering two formats — applying bold and then italic should produce bold-italic characters, not just italic.

**Why it matters:** BoldItalicSans is produced by composing BoldSans + ItalicSans. The system must correctly detect that a bold character is being italicized and upgrade it to the combined style, rather than just replacing bold with italic.

```javascript
test('boldSans + italicSans = boldItalicSans', () => {
    const afterBold   = applyFormatToText('hi', 'boldSans');
    const afterItalic = applyFormatToText(afterBold, 'italicSans');
    expect(afterItalic).toBe('𝙝𝙞'); // Mathematical Sans-Serif Bold Italic
});

test('italicSans + boldSans = boldItalicSans (order independent)', () => {
    const afterItalic = applyFormatToText('hi', 'italicSans');
    const afterBold   = applyFormatToText(afterItalic, 'boldSans');
    expect(afterBold).toBe('𝙝𝙞');
});

test('removing boldSans from boldItalicSans leaves italicSans', () => {
    const boldItalic = applyFormatToText(applyFormatToText('hi', 'boldSans'), 'italicSans');
    const onlyItalic = applyFormatToText(boldItalic, 'boldSans'); // toggle off bold
    expect(onlyItalic).toBe(maps.italicSans['h'] + maps.italicSans['i']);
});
```

**Composition creation caveat:** The composed format `boldItalicSans` must be created via composition (`boldSans` then `italicSans`), not by calling `applyFormatToText('hi', 'boldItalicSans')` directly, because the system resolves `boldItalicSans` through the composition chain, not as a standalone format name.

---

### Suite 10: Clear Format

**What it tests:** The `clearFormatText()` function must convert any styled Unicode text back to plain ASCII.

**The original bug:** The old `clearFormat()` only did:
```javascript
text.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
```

This only stripped combining diacritics (the underline overlay character U+0332). It had no effect on Unicode Mathematical characters. So `𝗮` (bold sans a) would remain `𝗮` after "clearing."

**The fix:** Iterate each character through `toPlain()` first, then strip diacritics:

```javascript
function clearFormatText(text) {
    let clean = '';
    for (const char of text) clean += toPlain(char);
    return clean.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}
```

The tests validate both behaviors:

```javascript
for (const style of STYLE_NAMES) {
    test(`clears ${style} formatting`, () => {
        const formatted = applyFormatToText('Hello', style);
        expect(clearFormatText(formatted)).toBe('Hello');
    });
}

test('clears underline (combining low line \\u0332)', () => {
    const underlined = 'H\u0332e\u0332l\u0332l\u0332o\u0332';
    expect(clearFormatText(underlined)).toBe('Hello');
});

test('clears full sentence with multiple formats', () => {
    const bold   = applyFormatToText('Hello', 'boldSans');
    const italic = applyFormatToText('World', 'italicSerif');
    expect(clearFormatText(bold + ' ' + italic)).toBe('Hello World');
});
```

---

### Suite 11: Auto-Emojify

**What it tests:** The `autoEmojifyText()` function appends an appropriate emoji after known "buzzwords" (growth, launch, fire, etc.).

```javascript
test('adds emoji after known buzzword', () => {
    expect(autoEmojifyText('growth is key')).toContain('growth 📈');
});

test('case-insensitive matching', () => {
    expect(autoEmojifyText('GROWTH matters')).toContain('GROWTH 📈');
});

test('unknown words are not changed', () => {
    expect(autoEmojifyText('banana is tasty')).toBe('banana is tasty');
});

test('non-buzzword words between emojis are unchanged', () => {
    const result = autoEmojifyText('fire safety');
    expect(result).toContain('fire 🔥');
    expect(result).not.toContain('safety 🔥');
});
```

---

### Suite 12: Shortcode Conversion

**What it tests:** `:rocket:` → 🚀, `:fire:` → 🔥, etc. Unknown shortcodes pass through unchanged.

```javascript
test(':rocket: converts to 🚀', () => {
    expect(convertShortcodesText("Let's :rocket: this!")).toBe("Let's 🚀 this!");
});

test('unknown shortcodes are unchanged', () => {
    expect(convertShortcodesText(':unknown:')).toBe(':unknown:');
});

test('multiple shortcodes in one string', () => {
    const result = convertShortcodesText(':rocket: to the moon :fire:');
    expect(result).toBe('🚀 to the moon 🔥');
});
```

---

### Suite 13: Edge Cases

**What it tests:** Boundary conditions — empty strings, digit round-trips, the Planck constant (ℎ), style switching, and `formatSetToString` stability.

```javascript
test('empty string returns empty string for any format', () => {
    expect(applyFormatToText('', 'boldSans')).toBe('');
    expect(clearFormatText('')).toBe('');
    expect(autoEmojifyText('')).toBe('');
});

test('italic serif h round-trips correctly (ℎ is Planck constant)', () => {
    // U+1D455 (italic h) is unassigned in Unicode; the fallback is U+210E (ℎ)
    expect(maps.italicSerif['h']).toBe('ℎ');
    expect(toPlain('ℎ')).toBe('h');
});

test('applying format to already-formatted text in different style replaces it', () => {
    const frakturText = applyFormatToText('Hello', 'fraktur');
    const boldText    = applyFormatToText(frakturText, 'boldSans');
    for (const c of 'Hello') {
        expect(boldText).toContain(maps.boldSans[c]);
    }
});

test('formatSetToString produces stable sort', () => {
    const set1 = new Set(['italicSans', 'boldSans']);
    const set2 = new Set(['boldSans', 'italicSans']);
    expect(formatSetToString(set1)).toBe(formatSetToString(set2));
});
```

**The Planck constant note:** In Unicode Mathematical Italic block (U+1D400–U+1D44F), the slot for lowercase italic h (U+1D455) is *permanently unassigned* because ℎ (U+210E, the Planck constant symbol) already existed in the Letterlike Symbols block and was deemed equivalent. Every correct implementation must map italic h to U+210E, not leave it blank.

---

## The Unicode Testing Challenge

Testing Unicode formatters is harder than testing regular string functions because:

### 1. Invisible characters look identical in code
`𝕮` (Bold Fraktur C, U+1D56E) and `ℂ` (Double-Struck C, U+2102) look similar in many fonts. Only the codepoint — and therefore the test assertion — reveals which is which.

### 2. Unassigned codepoints are not errors at runtime
JavaScript doesn't throw an exception when you assign `maps.fraktur['C'] = '\u{1D506}'`. The string is valid. It just renders as a tofu box (□) in environments that don't have a glyph for that codepoint. The original code had three such unassigned codepoints in the Fraktur map.

The round-trip test catches these indirectly: `toPlain('\u{1D506}')` won't find anything in the reverse map, so it returns the character unchanged — and `toPlain(maps.fraktur['C']) !== 'C'` fails the assertion.

### 3. Case confusion
`𝔷` (Fraktur lowercase z, U+1D537) and `ℨ` (Fraktur uppercase Z, U+2128) are different characters. The original code mapped uppercase Z to the lowercase glyph. Tests using both `maps.fraktur['Z']` and `maps.fraktur['z']` explicitly check they are different.

### 4. Cross-block contamination
Different Unicode blocks cover similar-looking characters. The original circular/double-struck map accidentally used Mathematical Bold Fraktur (U+1D56C–U+1D59F) for uppercase C–Z instead of the correct Mathematical Double-Struck (U+1D538–U+1D56B, with special cases at ℂ, ℍ, ℕ, ℙ, ℚ, ℝ, ℤ).

The cross-map collision tests catch this by verifying that fraktur and circular share no alpha characters.

---

## Bugs Found and Fixed

| # | Bug | Discovered By |
|---|-----|---------------|
| 1 | Fraktur R duplicated S's glyph (𝔖) | Intra-map duplicate + regression tests |
| 2 | Fraktur Z used lowercase glyph (𝔷) | Regression test |
| 3 | Fraktur C, H, I used unassigned codepoints | Round-trip test |
| 4 | Script uppercase B/E/F/H/I/L/M/R used italic chars | Cross-map collision + regression tests |
| 5 | Script lowercase e/g/o used italic chars | Cross-map collision + regression tests |
| 6 | italicSerif was identical to italicSans | Cross-map collision test |
| 7 | Circular uppercase C–Z used Bold Fraktur | Cross-map collision + regression tests |
| 8 | clearFormat() only stripped diacritics, not Unicode math chars | clearFormat suite |
| 9 | Toggle failed for multi-word selections (space confusion) | Toggle behavior suite |

**Bonus bugs fixed (UI/CSS, not test-discoverable):**
- Copy button invisible on mobile (viewport overflow)
- Emoji modal close button using `float: right` (outdated layout)

---

## Final Test Run

```
Test Suites: 13 passed, 13 total
Tests:       144 passed, 144 total
Snapshots:   0 total
Time:        ~0.8s
```

All 144 tests pass. The suite runs in under a second because it is pure Node.js — no browser, no DOM, no network.

---

## You Don't Need a Separate Test Automation Tool If You Have an AI Coding Assistant

This is the most important practical lesson from this project, and it deserves its own section.

The traditional view of adding tests to an existing codebase looks like this:

```
Step 1: Hire a QA engineer or assign a developer to testing
Step 2: Learn the testing framework and set it up
Step 3: Manually trace through the code to understand what to test
Step 4: Write tests, one by one, for each function
Step 5: Run tests, find failures, debug them
Step 6: Separately, investigate reported bugs
Step 7: Fix bugs, re-run tests, update as needed
```

Each step is a context switch. Each step requires dedicated time, expertise, and tooling decisions. For a side project or a small team, this overhead is often why testing never happens at all.

With an AI coding assistant like Claude Code, the entire pipeline collapses into a conversation:

```
You: "Analyze this codebase, add tests, and fix any bugs you find."

Claude Code:
  → Reads and understands the codebase (all files, not just the ones you point to)
  → Identifies the architectural blocker (inline JS = untestable)
  → Proposes and implements the extraction strategy (UMD module)
  → Designs the test strategy (13 suites, 144 tests)
  → Writes all test code
  → Discovers 9 bugs while writing tests
  → Fixes all bugs
  → Verifies every fix passes
  → Reports back with a complete summary
```

That is not a simplification. That is exactly what happened in one session.

---

### What an AI Assistant Replaces (and What It Doesn't)

**What Claude Code replaced in this project:**

| Traditional approach | What Claude Code did instead |
| --- | --- |
| Test automation engineer writing tests | Designed and wrote all 13 test suites |
| QA manual testing to find bugs | Found 9 bugs through static analysis + test design |
| Senior developer choosing architecture | Chose UMD pattern for browser/Node dual compatibility |
| Hours of boilerplate and framework setup | Set up Jest, package.json, and test runner in minutes |
| Separate bug report → investigation → fix cycle | Bug discovery and fix happened simultaneously |
| Code review to catch character map errors | Round-trip tests that validate all 520 combinations |

**What Claude Code did NOT replace:**

- **You deciding what the product should do.** The test strategy was grounded in what matters to users — does bold actually look bold? Does toggle actually toggle? That intent came from the product, not the AI.
- **You approving the plan before any code was written.** Claude Code proposed the architectural approach (UMD extraction) and waited for approval before implementing. Human judgment stayed in the loop on every consequential decision.
- **You verifying the results.** Running `npm test` and seeing 144 green checks is a human act. The AI cannot ship without a human seeing the output.
- **Domain knowledge review.** Understanding *why* U+1D455 is permanently unassigned, or *why* the circular style should use Double-Struck and not Bold Fraktur — that required Unicode specification knowledge that was applied judgment, not just code generation.

---

### The Real Shift: From "Write Tests" to "Describe What Good Looks Like"

The traditional test automation mindset asks: *"How do I write a test for this function?"*

The AI-assisted mindset asks: *"What does correct behavior look like, and what would broken behavior look like?"*

That is a fundamentally more useful question. When the answer to that question is:

- "Every letter should round-trip through the format map"
- "No two keys in the same map should produce the same output"
- "Applying a format twice should return the original text"

...Claude Code turns those descriptions directly into executable tests. You describe the invariants. The AI writes the assertions.

This is why the test suite caught bugs that years of manual use missed. A human writing tests would write *"test that bold works"* — they'd type `hello`, click Bold, see `𝗵𝗲𝗹𝗹𝗼`, and call it done. An AI, given the invariant *"every letter must round-trip"*, mechanically checks all 52 letters across all 10 styles — and finds that `toPlain(maps.fraktur['C'])` doesn't return `'C'` because the codepoint is unassigned.

Manual testing validates what you remember to check. Invariant tests validate everything.

---

### What This Means for How You Work

**You don't need a dedicated test automation sprint.** Tests are no longer a phase that happens "after development." With Claude Code, you describe a concern ("I'm not sure the character maps are correct") and tests that verify that concern exist within minutes.

**You don't need deep framework knowledge.** You don't need to know Jest's API, how to structure `describe` blocks, or how to configure `package.json`. Describe what you want verified; the AI handles the mechanics.

**You don't need to choose between "test first" and "test later."** The AI can analyze existing code and write tests that match its current behavior *and* its intended behavior — simultaneously surfacing where they diverge. That is what happened here: the tests revealed that the "italic serif" style was identical to "italic sans" because the reverse map proved it.

**Your testing cost drops from weeks to hours.** This project: one session. 144 tests. 9 bugs fixed. A test suite that now runs in 0.8 seconds on every change and will catch regressions forever.

---

### The One Thing You Still Need to Provide

A clear description of what *correct* means for your domain.

For this project, that meant knowing:

- Unicode mathematical character blocks have gaps where specific codepoints are unassigned
- Each formatting style should be uniquely identifiable (no collisions between maps)
- Applying a format twice should be a toggle, not an accumulation
- A "clear" operation should remove all styling, not just diacritics

You brought the domain knowledge. Claude Code brought the test engineering. Neither is sufficient alone. Together, they produced a test suite that is more thorough than most manually-written suites would be — because the AI applies the invariant mechanically, without fatigue, across the full input space.

That is the correct mental model for AI-assisted testing: **you define "correct," the AI operationalizes it.**

---

## Where This Approach Applies: Real-World Use Cases

The pattern used here — extract pure logic to a UMD module, test it in Node.js with Jest — is not specific to Unicode formatters. It applies to any web application that has non-trivial business logic embedded in inline JavaScript. Here are common scenarios where this exact approach delivers immediate value.

---

### 1. Character Encoding and Transliteration Tools

**What:** Browser tools that convert text between scripts or encodings — romanization of Japanese (Hepburn), Cyrillic to Latin, Morse code converters, phonetic transcription, Braille encoding, or any lookup-table-driven character substitution.

**Why the same pattern works:** The core is identical — a map of input characters to output characters, a reverse map for decoding, and bijective (reversible) conversion functions. The round-trip test (`decode(encode(c)) === c`) and the intra-map duplicate check are directly reusable.

```javascript
// Example: Testing a Hepburn romanization map
test('no two kana map to the same romaji', () => {
    const seen = new Set();
    for (const [kana, romaji] of Object.entries(hepburnMap)) {
        expect(seen.has(romaji)).toBe(false);
        seen.add(romaji);
    }
});

test('round-trip: romaji → kana → romaji', () => {
    for (const [kana, romaji] of Object.entries(hepburnMap)) {
        expect(reverseHepburn[romaji]).toBe(kana);
    }
});
```

---

### 2. E-Commerce Pricing Engines

**What:** Discount calculators, promo code validators, tier-based pricing logic, and shipping cost estimators embedded in checkout pages. These are often written as inline `<script>` tags or Shopify theme JS — completely untested.

**Why the same pattern works:** Pricing logic is pure functions — `calculateTotal(cart, coupon)` takes data in and returns a number out. It doesn't need the DOM. Moving it to a `pricing.js` module with UMD export makes it instantly testable.

```javascript
// Example: Testing discount application rules
test('percentage discount is capped at item price', () => {
    expect(applyDiscount(10, { type: 'percent', value: 150 })).toBe(0);
});

test('free shipping activates above threshold', () => {
    expect(calculateShipping({ subtotal: 75, threshold: 50 })).toBe(0);
    expect(calculateShipping({ subtotal: 49, threshold: 50 })).toBeGreaterThan(0);
});

test('stacking coupons does not produce negative total', () => {
    const result = applyMultipleCoupons(100, [coupon30, coupon80]);
    expect(result).toBeGreaterThanOrEqual(0);
});
```

**Risk without tests:** A pricing bug is both a financial loss (undercharging) and a legal risk (overcharging customers). Test coverage here pays for itself immediately.

---

### 3. Form Validation Libraries

**What:** Password strength checkers, email format validators, phone number formatters, credit card validators, and business-rule validators (e.g., "age must be 18+", "company registration number format") embedded in sign-up or checkout forms.

**Why the same pattern works:** Validators are the purest of pure functions — `validate(value)` returns `true/false` or an error message. They are completely independent of the DOM.

```javascript
// Example: Testing a password strength checker
test('password with less than 8 chars is weak', () => {
    expect(checkStrength('abc')).toBe('weak');
});

test('password with uppercase, lowercase, number, symbol is strong', () => {
    expect(checkStrength('P@ssw0rd!')).toBe('strong');
});

test('all common passwords are rejected', () => {
    for (const pw of COMMON_PASSWORDS) {
        expect(isCommonPassword(pw)).toBe(true);
    }
});
```

**Bonus:** The same validation module can be `require()`d in a Node.js API server for server-side validation — one source of truth, two environments.

---

### 4. Text Transformation Pipelines

**What:** Markdown-to-HTML converters, BBCode parsers, template engines (e.g., Mustache/Handlebars-like substitution), word count tools, or readability score calculators embedded in CMS admin interfaces or browser-based editors (like TinyMCE plugins or WordPress block plugins).

**Why the same pattern works:** Text in → text out. No DOM. Testing a Markdown converter with property tests (e.g., "every `**word**` becomes `<strong>word</strong>`") is straightforward and prevents rendering regressions when you update the parser.

```javascript
test('bold markdown converts to <strong>', () => {
    expect(renderMarkdown('**hello**')).toBe('<strong>hello</strong>');
});

test('headings convert to correct h-level', () => {
    expect(renderMarkdown('## Section')).toContain('<h2>');
    expect(renderMarkdown('### Sub')).toContain('<h3>');
});

test('unrecognized syntax passes through unchanged', () => {
    expect(renderMarkdown('plain text')).toBe('<p>plain text</p>');
});
```

---

### 5. Browser-Based Games and Puzzle Logic

**What:** Game scoring algorithms, move validators (chess, checkers, Sudoku), AI decision trees, puzzle state machines, or physics simulations (simplified collision detection, trajectory math) embedded in `<script>` tags in game HTML pages.

**Why the same pattern works:** Game logic is almost always pure — `isValidMove(board, from, to)` doesn't draw on the canvas; it just returns `true` or `false`. Extracting game logic allows you to write thousands of test cases covering edge cases without running a browser.

```javascript
// Example: Testing chess move validation
test('pawn cannot move backwards', () => {
    expect(isValidMove(board, {from: 'e4', to: 'e3'}, 'white')).toBe(false);
});

test('king cannot move into check', () => {
    const board = setupBoard(['Ke1', 'Rd8']); // black rook on d8
    expect(isValidMove(board, {from: 'e1', to: 'd1'}, 'white')).toBe(false);
});
```

**High value:** Game bugs discovered before release avoid negative reviews; game logic is complex enough that manual testing misses many edge cases.

---

### 6. Data Import / Parsing Utilities

**What:** CSV/TSV parsers, JSON transformers, field normalizers ("trim whitespace", "normalize phone format", "convert date format"), and data deduplication logic embedded in browser-based data upload or migration tools.

**Why the same pattern works:** Parsers are pure text-processing functions. Testing a CSV parser with known inputs and expected outputs is fast, deterministic, and catches encoding edge cases (e.g., quoted fields containing commas, Unicode in headers, BOM characters).

```javascript
test('quoted field with embedded comma is not split', () => {
    const row = parseCSVRow('"Smith, John",30,London');
    expect(row[0]).toBe('Smith, John');
    expect(row).toHaveLength(3);
});

test('empty fields produce empty strings not undefined', () => {
    const row = parseCSVRow('a,,c');
    expect(row[1]).toBe('');
});
```

---

### 7. Scientific / Unit Converter Tools

**What:** Currency converters, unit conversion tools (kg↔lb, °C↔°F, km↔mi), tax calculators, mortgage calculators, or any mathematical formula embedded in informational web pages.

**Why the same pattern works:** Conversions are the definition of pure functions. Property tests verify mathematical identities (round-tripping, identity conversions, limit cases).

```javascript
test('Celsius to Fahrenheit: 0°C = 32°F', () => {
    expect(celsiusToFahrenheit(0)).toBe(32);
});

test('Fahrenheit to Celsius round-trip', () => {
    for (const temp of [-40, 0, 37, 100]) {
        expect(celsiusToFahrenheit(fahrenheitToCelsius(temp))).toBeCloseTo(temp);
    }
});

test('conversion is invertible: C→F→C = original', () => {
    // Same principle as the Unicode round-trip test
    expect(fahrenheitToCelsius(celsiusToFahrenheit(25))).toBeCloseTo(25);
});
```

---

### 8. Color / Design Utilities

**What:** Color space converters (HEX↔RGB↔HSL↔HSV), contrast ratio calculators (for WCAG accessibility compliance), color palette generators, or gradient interpolation tools embedded in browser-based design tools.

**Why the same pattern works:** Color math is pure. WCAG contrast ratio has an exact formula; testing it prevents accessibility regressions when you update the color logic. Round-trip tests verify that `hex → rgb → hex` produces the original hex.

```javascript
test('hex to RGB: #FF0000 = {r:255, g:0, b:0}', () => {
    expect(hexToRGB('#FF0000')).toEqual({ r: 255, g: 0, b: 0 });
});

test('WCAG contrast ratio: white on black = 21:1', () => {
    expect(contrastRatio('#FFFFFF', '#000000')).toBeCloseTo(21, 0);
});

test('round-trip: hex → rgb → hex', () => {
    for (const hex of ['#1A2B3C', '#AABBCC', '#FF6600']) {
        expect(rgbToHex(hexToRGB(hex))).toBe(hex.toUpperCase());
    }
});
```

---

## Best Practices

The following practices were applied in this project and generalize across all the use cases above. Think of this as a checklist for retrofitting tests onto any browser-based JavaScript application.

---

### Architecture

**BP-1: Separate pure logic from DOM manipulation before writing a single test.**
The entire effort of adding tests starts with one question: *"Which functions don't touch the DOM?"* Those functions are your testing surface. Move them to a `.js` module first. Everything else follows.

```
Before:   index.html (2000 lines, inline JS, untestable)
After:    formatter.js (pure logic, testable) + index.html (DOM wiring only)
```

**BP-2: Use UMD until you have a build step.**
If your project has no bundler (Webpack, Vite, Rollup), UMD is the correct module format. It works as a plain `<script>` in the browser and as `require()` in Node.js — no transpilation needed.

```javascript
(function (root, factory) {
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = factory(); // Node.js
    } else {
        Object.assign(root, factory()); // Browser window
    }
}(typeof self !== 'undefined' ? self : this, function () {
    // your pure logic here
    return { /* public API */ };
}));
```

If you already have a bundler, prefer ES modules (`export`/`import`) and configure Jest's `transform` accordingly.

**BP-3: Return a minimal public API.**
Only export what tests need to verify, not internal implementation details. This gives you freedom to refactor internals without breaking tests.

```javascript
// Good: export the contract
return { maps, toPlain, detectFormats, applyFormatToText, clearFormatText };

// Bad: export everything, tests couple to internals
return { maps, reverseMaps, _buildReverseMap, _normalizeChar, ... };
```

---

### Test Design

**BP-4: Use data-driven (parameterized) tests for repetitive cases.**
Never copy-paste a test block to cover each item in a list. Use a loop. When you add a new style/format/rule, one array update covers all suites automatically.

```javascript
// Bad: copy-pasted
test('boldSans has all lowercase', () => { ... });
test('italicSans has all lowercase', () => { ... });
test('fraktur has all lowercase', () => { ... });

// Good: parameterized
for (const style of STYLE_NAMES) {
    test(`${style} has all lowercase`, () => { ... });
}
```

**BP-5: Test data integrity separately from behavior.**
Split your tests into two categories:

- **Data tests** — is the map correct? Are all entries present? Are there duplicates?
- **Behavior tests** — does the function do the right thing with correct data?

Data tests catch *configuration errors*. Behavior tests catch *logic errors*. They fail for different reasons and need different fixes.

**BP-6: Use round-trip tests for any bijective (reversible) function.**
If your system has `encode` and `decode` (or `apply` and `reverse`), write `decode(encode(x)) === x` as a loop over the full input space. This single pattern catches unassigned codepoints, wrong characters, case confusion, and missing entries — all at once.

```javascript
// Covers 10 styles × 52 letters = 520 assertions in 10 lines
for (const style of STYLE_NAMES) {
    test(`${style}: round-trip`, () => {
        for (const c of ALL_ALPHA) {
            expect(toPlain(maps[style][c])).toBe(c);
        }
    });
}
```

**BP-7: Test invariants, not just specific values.**
An invariant is a property that must always hold, regardless of the specific input. "No duplicates within a map" is an invariant. "No collisions between maps" is an invariant. These cover the entire input space, not just the cases you remembered to check.

| Instead of... | Test the invariant... |
| --- | --- |
| `expect(maps.fraktur['a']).not.toBe(maps.fraktur['b'])` | All values in the map are unique (Set check) |
| `expect(maps.italicSans['a']).not.toBe(maps.italicSerif['a'])` | Two maps share no alpha characters (intersection check) |

**BP-8: Name regression tests after the bug, not the fix.**
A test name like `"fraktur R is ℜ"` is good. A test name like `"fraktur R is ℜ (U+211C), not S duplicate 𝔖"` is better — it documents *what broke*, not just *what is correct now*. Six months later, when someone sees this test fail, they immediately understand the historical context.

**BP-9: Use both `.toBe()` and `.not.toBe()` in regression tests.**

```javascript
// Documents both the correct value AND the wrong value it used to be
test('fraktur R is ℜ (U+211C), not S duplicate 𝔖', () => {
    expect(maps.fraktur['R']).toBe('ℜ');           // correct
    expect(maps.fraktur['R']).not.toBe(maps.fraktur['S']); // the original bug
});
```

**BP-10: Collect all failures before asserting.**
When testing a property over a list (e.g., checking for duplicates), gather all violations first and assert the complete list is empty. This reports every duplicate at once rather than failing on the first one, making debugging faster.

```javascript
// Bad: stops on first duplicate
for (const [key, val] of Object.entries(maps[style])) {
    expect(seen.has(val)).toBe(false); // first failure stops the test
    seen.add(val);
}

// Good: reports all duplicates
const duplicates = [];
for (const [key, val] of Object.entries(maps[style])) {
    if (seen.has(val)) duplicates.push({ key, val });
    seen.add(val);
}
expect(duplicates).toEqual([]); // prints all duplicates if it fails
```

---

### Test Environment

**BP-11: Use `testEnvironment: "node"` unless you need the DOM.**
By default, Jest (via jsdom) simulates a browser environment. This adds startup overhead and pulls in a large dependency. If your logic is pure (no `document`, no `window`, no `fetch`), explicitly set `"testEnvironment": "node"` in `package.json`. Tests run faster and failures are cleaner.

```json
"jest": {
  "testEnvironment": "node"
}
```

**BP-12: Keep test files UTF-8 encoded when testing Unicode.**
Jest reads test files as UTF-8 by default. Unicode string literals like `'𝗮'` in test assertions work correctly, but make sure your editor saves the file as UTF-8 (not Latin-1 or Windows-1252). Also add a UTF-8 BOM if your CI environment has locale issues.

**BP-13: Add `npm test` to your CI pipeline from day one.**
A test suite that only runs locally provides weak guarantees. Add it to GitHub Actions, GitLab CI, or your pipeline of choice so every pull request is validated automatically:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - run: npm ci
      - run: npm test
```

**BP-14: Add coverage reporting but don't worship the number.**
`npm run test:coverage` generates a coverage report. It tells you which lines of `js/formatter.js` were exercised. Aim for 100% on critical paths (the character maps, the core transform functions) but don't add meaningless tests just to hit 100% overall.

---

### Maintenance

**BP-15: Write the test before fixing the bug (when possible).**
When a new bug is reported:

1. Write a failing test that reproduces it
2. Fix the bug
3. Confirm the test now passes

This ensures the bug is documented, reproducible, and cannot silently regress. It's the discipline that makes regression suites grow naturally.

**BP-16: Keep `STYLE_NAMES` (or equivalent constants) as a single source of truth.**
All parameterized tests reference the same `STYLE_NAMES` array. When a new formatting style is added to the application, adding its name to `STYLE_NAMES` automatically enrolls it in all 13 test suites — completeness, duplicates, collisions, round-trips, toggle, and clear. Zero additional test code required.

**BP-17: Document surprising constraints in test comments.**
Not everything is obvious. The Planck constant (ℎ, U+210E) as the fallback for italic h, or the fact that U+1D455 is permanently unassigned — these are facts that future maintainers will not know. Put them in the test, where they are impossible to miss:

```javascript
test('italic serif h round-trips correctly (ℎ is Planck constant)', () => {
    // U+1D455 (mathematical italic h) is permanently unassigned in Unicode
    // because ℎ (U+210E, Planck constant) pre-existed and is deemed equivalent.
    // This means EVERY implementation must use U+210E, not U+1D455.
    expect(maps.italicSerif['h']).toBe('ℎ');
    expect(toPlain('ℎ')).toBe('h');
});
```

---

## Key Takeaways

### 1. Extract logic before you can test it
If your business logic lives inside a `<script>` tag in HTML, the first step to testability is extracting it to a separate `.js` file. Use the UMD pattern to stay compatible with both browser and Node.js.

### 2. Data integrity tests are undervalued
The Map Completeness, Intra-Map Duplicates, and Cross-Map Collision suites are not testing behavior — they are testing *data*. They are cheap to write and caught the majority of bugs in this codebase.

### 3. Round-trip tests catch invisible errors
`toPlain(maps[style][c]) === c` is a one-liner that validates the entire map + reverse-map system for 520 combinations (10 styles × 52 letters). It caught three unassigned Unicode codepoints and one case confusion bug.

### 4. Regression tests should name the bug
The Specific Bug Regression suite uses test names like `"fraktur R is ℜ (U+211C), not S duplicate 𝔖"`. This is intentional — it turns the test into permanent documentation of what the bug was, why it matters, and what the correct value is.

### 5. Composition is a first-class concept
`boldItalicSans` is not a map entry — it is the mathematical intersection of `boldSans` and `italicSans`. Testing composition separately from basic application reveals whether the format system is correctly modeling the underlying Unicode block structure.

### 6. Test your invariants, not just your outputs
Many of the suites test properties (no duplicates, no collisions, round-trip identity) rather than specific values. This is more powerful: a property test covers all 52 letters × all 10 styles automatically, whereas a spot-check test only covers the letters you thought to include.

---

## Resources

- [Unicode Mathematical Alphanumeric Symbols block (U+1D400–U+1D7FF)](https://www.unicode.org/charts/PDF/U1D400.pdf)
- [Unicode Letterlike Symbols block (U+2100–U+214F)](https://www.unicode.org/charts/PDF/U2100.pdf)
- [Jest documentation](https://jestjs.io/docs/getting-started)
- [UMD (Universal Module Definition) pattern](https://github.com/umdjs/umd)
- [Source code](https://github.com/gsaravanan/post-formatter)

---

*Test suite authored with [Claude Code](https://claude.ai/claude-code). Jest 29. All 144 tests pass on Node.js 22 (LTS).*
