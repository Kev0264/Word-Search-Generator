# Bigger Swings

Ideas discussed for differentiating the books further, deliberately deferred
since they need real new engineering rather than building on what exists.
Not needed yet -- revisit once the current book format is proven out.

- [ ] **Second puzzle type mixed in.** Alternate word searches with a
      cryptogram or word-scramble page for variety within one book. Needs a
      new puzzle-generation + rendering path, not just a new layout.
- [ ] **Per-theme visual motif.** A small line-art icon or decorative border
      matching each puzzle's theme (e.g. a paw print for "Animals"). Needs an
      art asset pipeline (a icon library or generated art) we don't have.
- [ ] **Personalized/custom editions.** Per-copy personalization (a name on
      the title page, etc.) isn't naturally supported by KDP's standard
      print-on-demand flow; would need a separate automation/ordering path.
- [ ] **Series branding.** Consistent cover/interior branding across a
      numbered volume series, so one book's readers convert to the next.
      Mostly a content/marketing exercise, not a generator feature -- revisit
      once there's more than one real book.
- [ ] **Companion digital tool.** A QR code linking to hints, a digital
      timer, or a leaderboard. Real scope creep beyond a PDF generator;
      only worth it if the print book takes off.

# Smaller ideas not yet scheduled

- [ ] Redistribute the last 4-up answer-key page's mini-grids when it has
      fewer than 4 entries (currently top-aligned, leaving the bottom half
      empty on the final page for a puzzle count that isn't a multiple of 4).
- [ ] **Optional `Category` column + `--alphabetize` CLI flag.** Came up
      wanting to group the national parks book into a "National Parks"
      section and a separate section for the broader topics, with each
      section's puzzles sorted alphabetically and the section names visible
      in the TOC. Solved for now by just pre-sorting the CSV by hand (parks
      A-Z, then the other topics), but a real feature would look like:
    - Add an optional `Category` column to the CSV (position: right after
      `Trivia`, before the word columns -- `Title,Trivia,Category,Words`).
      Needs `read_puzzle_csv()` to detect it (e.g. check whether the header's
      3rd cell says "Category", case-insensitive) so old 3-column CSVs
      keep working unchanged; add a `category: str | None` field to
      `PuzzleSpec`.
    - If no row has a category, behave exactly as today (flat list, no
      section dividers, no change to the TOC).
    - If any row has a category, group puzzles into one section per
      distinct category value, each with its own recto-forced section
      divider page (like the existing "Answer Keys" divider) and its own
      labeled entry in the TOC. Puzzles with a blank category get bucketed
      into a shared fallback section -- needs a friendlier label than
      "Uncategorized" (candidate: "More to Explore"), and maybe let it be
      overridden via a CLI flag.
    - Add an `--alphabetize` flag: when set, sort categories alphabetically
      by name and sort puzzles alphabetically by title within each category
      (or just alphabetize the flat list by title if there are no
      categories at all). When unset, preserve the CSV's existing order --
      categories in order of first appearance, puzzles in their existing
      relative order within each category.
    - Rendering-wise, `_render_toc_page`/`render_toc_pages` need a second
      row style (bold category heading, no checkbox) alongside the existing
      checkbox-and-title puzzle row, and the TOC's reserved page count needs
      to account for one extra row per category heading.
