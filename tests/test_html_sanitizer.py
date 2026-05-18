from app.utils.html_sanitizer import sanitize_html


def test_sanitize_html_strips_span_tags():
    raw = '<p>Recommendation <span style="color:red">with span</span> and <strong>bold</strong>.</p>'
    cleaned = sanitize_html(raw)

    assert '<span' not in cleaned
    assert '</span>' not in cleaned
    assert 'Recommendation with span and <strong>bold</strong>.' in cleaned
