import pytest

import metrics


@pytest.mark.parametrize("raw,expected", [
    ("أنا  رايح   السوق!", "انا رايح السوق"),          # alef unified, punctuation, spaces
    ("مَدْرَسَةٌ", "مدرسه"),                            # harakat removed, ta marbuta -> ha
    ("علـــى", "علي"),                                 # tatweel removed, alef maqsura -> ya
    ("৫০ টাকা।", "50 টাকা"),                           # Bangla digits, danda removed
    ("٣ ريال", "3 ريال"),                              # Arabic-Indic digits
    ("আমি কি যাব?", "আমি কি যাব"),                     # Bangla vowel signs kept
    ("Hello, World", "hello world"),
])
def test_normalize(raw, expected):
    assert metrics.normalize(raw) == expected


def test_cer_identical_after_normalization():
    assert metrics.cer("أبغى أروح السوق.", "ابغي اروح السوق") == 0.0
    assert metrics.cer("৫০ টাকা", "50 টাকা।") == 0.0


def test_cer_and_wer_bangla():
    ref = "আমি বাজারে যাব"
    hyp = "আমি বাজার যাব"
    assert metrics.wer(ref, hyp) == pytest.approx(1 / 3)
    assert metrics.cer(ref, hyp) == pytest.approx(1 / len(metrics.normalize(ref)))


def test_cer_arabic_word_missing():
    assert metrics.wer("وش تبغى تاكل", "وش تاكل") == pytest.approx(1 / 3)


def test_cer_empty_reference():
    assert metrics.cer("", "") == 0.0
    assert metrics.cer("", "x") == 1.0


def test_chrf_bounds():
    assert metrics.chrf("هذا بكم؟", "هذا بكم؟") == pytest.approx(100.0)
    assert metrics.chrf("هذا بكم؟", "") == 0.0
    assert metrics.corpus_chrf([], []) is None


def test_percentiles():
    xs = list(range(1, 101))
    assert metrics.percentile(xs, 50) == pytest.approx(50.5)
    assert metrics.percentile(xs, 95) == pytest.approx(95.05)
    assert metrics.percentile([7], 95) == 7
    assert metrics.percentile([], 50) is None
    assert metrics.mean([1, None, 3]) == 2
