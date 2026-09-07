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
- [ ] Consider a `--large-print` variant of the answer-key section (currently
      only the puzzle pages, title page, TOC, and front matter scale text).
