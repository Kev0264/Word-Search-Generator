from word_search.profanity import MIN_BLOCKED_WORD_LENGTH, find_blocked_words, load_blocklist


def test_load_blocklist_only_contains_clean_single_word_entries():
    blocklist = load_blocklist()
    assert len(blocklist) > 100
    for word in blocklist:
        assert word.isalpha()
        assert word.isupper()
        assert len(word) >= MIN_BLOCKED_WORD_LENGTH


def test_find_blocked_words_returns_empty_for_a_boring_grid():
    grid = [["Q"] * 10 for _ in range(10)]
    assert find_blocked_words(grid) == []


def test_find_blocked_words_detects_a_forward_match_in_a_row():
    word = min(load_blocklist(), key=len)
    row = list(word) + ["Q"] * 6
    grid = [row]

    matches = find_blocked_words(grid)

    assert any(found == word for found, _ in matches)


def test_find_blocked_words_detects_a_backwards_match_in_a_row():
    word = min(load_blocklist(), key=len)
    row = list(word[::-1]) + ["Q"] * 6
    grid = [row]

    matches = find_blocked_words(grid)

    assert any(found == word for found, _ in matches)


def test_find_blocked_words_detects_a_diagonal_match():
    word = min(load_blocklist(), key=len)
    n = len(word) + 4
    grid = [["Q"] * n for _ in range(n)]
    for i, ch in enumerate(word):
        grid[i][i] = ch

    matches = find_blocked_words(grid)

    assert any(found == word for found, _ in matches)
