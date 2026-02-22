from url_utils import normalize_url


class TestNormalizeUrl:
    def test_lowercases_host(self):
        assert normalize_url("https://SongKick.COM/foo") == "https://songkick.com/foo"

    def test_strips_www(self):
        assert (
            normalize_url("https://www.songkick.com/foo") == "https://songkick.com/foo"
        )

    def test_strips_www_case_insensitive(self):
        assert (
            normalize_url("https://WWW.songkick.com/foo") == "https://songkick.com/foo"
        )

    def test_removes_trailing_slash(self):
        assert (
            normalize_url("https://songkick.com/concerts/")
            == "https://songkick.com/concerts"
        )

    def test_keeps_root_slash(self):
        assert normalize_url("https://songkick.com/") == "https://songkick.com/"

    def test_removes_default_http_port(self):
        assert normalize_url("http://songkick.com:80/foo") == "http://songkick.com/foo"

    def test_removes_default_https_port(self):
        assert (
            normalize_url("https://songkick.com:443/foo") == "https://songkick.com/foo"
        )

    def test_keeps_non_default_port(self):
        assert (
            normalize_url("https://songkick.com:8080/foo")
            == "https://songkick.com:8080/foo"
        )

    def test_removes_utm_params(self):
        url = "https://songkick.com/event?utm_source=twitter&utm_medium=social&id=123"
        assert normalize_url(url) == "https://songkick.com/event?id=123"

    def test_removes_fbclid(self):
        url = "https://songkick.com/event?fbclid=abc123&id=456"
        assert normalize_url(url) == "https://songkick.com/event?id=456"

    def test_removes_gclid(self):
        url = "https://songkick.com/event?gclid=xyz&id=789"
        assert normalize_url(url) == "https://songkick.com/event?id=789"

    def test_removes_all_tracking_leaves_clean(self):
        url = "https://songkick.com/event?utm_source=x&utm_medium=y&fbclid=z"
        assert normalize_url(url) == "https://songkick.com/event"

    def test_preserves_meaningful_query_params(self):
        url = "https://songkick.com/event?id=123&city=paris"
        normalized = normalize_url(url)
        assert "id=123" in normalized
        assert "city=paris" in normalized

    def test_drops_fragment(self):
        assert (
            normalize_url("https://songkick.com/event#details")
            == "https://songkick.com/event"
        )

    def test_identical_urls_match(self):
        a = "https://www.songkick.com/concerts/123/?utm_source=email"
        b = "https://songkick.com/concerts/123"
        assert normalize_url(a) == normalize_url(b)

    def test_different_paths_dont_match(self):
        a = "https://songkick.com/concerts/123"
        b = "https://songkick.com/concerts/456"
        assert normalize_url(a) != normalize_url(b)

    def test_defaults_to_https_when_no_scheme(self):
        # urlparse treats schemeless URLs oddly — the whole thing becomes the path
        # This documents current behavior rather than asserting ideal behavior
        result = normalize_url("songkick.com/foo")
        assert result.startswith("https://")
