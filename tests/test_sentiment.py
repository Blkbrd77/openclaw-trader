"""Tests for OpenClaw sentiment analyzer."""



def test_classify_positive():
    from sentiment import classify_sentiment
    label, confidence = classify_sentiment(0.5)
    assert label == "positive"
    assert confidence > 0


def test_classify_negative():
    from sentiment import classify_sentiment
    label, confidence = classify_sentiment(-0.5)
    assert label == "negative"
    assert confidence > 0


def test_classify_neutral():
    from sentiment import classify_sentiment
    label, confidence = classify_sentiment(0.0)
    assert label == "neutral"


def test_associate_stocks_tesla():
    from sentiment import associate_stocks
    stocks = associate_stocks("Tesla shares surge after earnings beat expectations")
    assert "TSLA" in stocks


def test_associate_stocks_multiple():
    from sentiment import associate_stocks
    stocks = associate_stocks("Kratos and AeroVironment win defense contract")
    assert "KTOS" in stocks
    assert "AVAV" in stocks


def test_associate_stocks_none():
    from sentiment import associate_stocks
    stocks = associate_stocks("The weather is nice today")
    assert len(stocks) == 0


def test_analyzer_creation():
    from sentiment import get_analyzer
    analyzer = get_analyzer()
    assert analyzer is not None
    # Check financial terms were added
    assert "upgrade" in analyzer.lexicon
    assert "downgrade" in analyzer.lexicon


def test_analyze_article():
    from sentiment import get_analyzer, analyze_article
    analyzer = get_analyzer()
    article = {
        "title": "Tesla stock surges after record earnings beat",
        "description": "Strong growth drives bullish sentiment",
        "source": "Test",
        "published": "2026-02-27",
    }
    result = analyze_article(analyzer, article)
    assert result["sentiment"] == "positive"
    assert result["compound_score"] > 0
    assert "TSLA" in result["associated_stocks"]


def test_analyze_negative_article():
    from sentiment import get_analyzer, analyze_article
    analyzer = get_analyzer()
    article = {
        "title": "Joby Aviation stock crashes after FAA delays certification",
        "description": "Investors bearish on grounded fleet and lawsuit concerns",
        "source": "Test",
        "published": "2026-02-27",
    }
    result = analyze_article(analyzer, article)
    assert result["sentiment"] == "negative"
    assert result["compound_score"] < 0
    assert "JOBY" in result["associated_stocks"]
