from unittest.mock import Mock, patch

import pytest

from show_extractor import ShowExtractor


class TestBotProtectionDetection:
    def test_raises_on_403_warning(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Warning: Target URL returned error 403: Forbidden\nSome content",
            raise_for_status=Mock(),
        )

        with pytest.raises(
            ValueError, match="Site blocked access \\(bot protection\\)"
        ):
            extractor._fetch_page_markdown("https://example.com/event")

    def test_raises_on_captcha_warning(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Warning: This page maybe requiring CAPTCHA, please make sure you are authorized",
            raise_for_status=Mock(),
        )

        with pytest.raises(
            ValueError, match="Site blocked access \\(bot protection\\)"
        ):
            extractor._fetch_page_markdown("https://example.com/event")

    def test_returns_content_when_no_bot_protection(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Title: Cool Concert\n\nArtist: The Band\nVenue: The Spot",
            raise_for_status=Mock(),
        )

        result = extractor._fetch_page_markdown("https://example.com/event")
        assert result == "Title: Cool Concert\n\nArtist: The Band\nVenue: The Spot"


class TestParseJson:
    def test_parses_clean_json(self):
        text = '{"artists": ["The Band"], "venue": "The Spot", "date": "2026-03-15"}'
        result = ShowExtractor._parse_json(text)
        assert result == {
            "artists": ["The Band"],
            "venue": "The Spot",
            "date": "2026-03-15",
        }

    def test_parses_json_with_code_fences(self):
        text = '```json\n{"artists": ["The Band"], "venue": "The Spot", "date": "2026-03-15"}\n```'
        result = ShowExtractor._parse_json(text)
        assert result["artists"] == ["The Band"]

    def test_parses_json_with_surrounding_text(self):
        text = 'Here is the data:\n{"artists": ["The Band"], "venue": "The Spot", "date": "2026-03-15"}\nDone!'
        result = ShowExtractor._parse_json(text)
        assert result["venue"] == "The Spot"

    def test_raises_on_invalid_json(self):
        with pytest.raises(Exception):
            ShowExtractor._parse_json("not json at all")


class TestExtractShowInfoWithLlm:
    def test_returns_parsed_dict(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"artists": ["The Band"], "venue": "The Spot", "date": "2026-03-15"}'
                    )
                )
            ]
        )

        result = extractor._extract_show_info_w_llm("some markdown content")
        assert result == {
            "artists": ["The Band"],
            "venue": "The Spot",
            "date": "2026-03-15",
        }

    def test_returns_none_on_empty_response(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=None))]
        )

        result = extractor._extract_show_info_w_llm("some markdown content")
        assert result is None


class TestExtractShow:
    def test_returns_submission_on_success(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Title: Cool Concert\n\nArtist info here",
            raise_for_status=Mock(),
        )
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"artists": ["The Band"], "venue": "The Spot", "date": "2026-03-15"}'
                    )
                )
            ]
        )

        result = extractor.extract_show("https://example.com/event")

        assert result is not None
        assert result.artists == ["The Band"]
        assert result.venue == "The Spot"
        assert result.date == "2026-03-15"
        assert result.ticket_url == "https://example.com/event"

    def test_returns_none_on_empty_llm_response(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Some content",
            raise_for_status=Mock(),
        )
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=None))]
        )

        result = extractor.extract_show("https://example.com/event")
        assert result is None

    def test_raises_on_missing_artists(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Some content",
            raise_for_status=Mock(),
        )
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"artists": null, "venue": "The Spot", "date": "2026-03-15"}'
                    )
                )
            ]
        )

        with pytest.raises(ValueError, match="Could not extract artists"):
            extractor.extract_show("https://example.com/event")

    def test_raises_on_missing_venue(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Some content",
            raise_for_status=Mock(),
        )
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"artists": ["The Band"], "venue": null, "date": "2026-03-15"}'
                    )
                )
            ]
        )

        with pytest.raises(ValueError, match="Could not extract venue"):
            extractor.extract_show("https://example.com/event")

    def test_raises_on_missing_date(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Some content",
            raise_for_status=Mock(),
        )
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"artists": ["The Band"], "venue": "The Spot", "date": null}'
                    )
                )
            ]
        )

        with pytest.raises(ValueError, match="Could not extract date"):
            extractor.extract_show("https://example.com/event")

    def test_raises_listing_all_missing_fields(self):
        extractor = ShowExtractor.__new__(ShowExtractor)
        extractor._http = Mock()
        extractor._http.get.return_value = Mock(
            text="Some content",
            raise_for_status=Mock(),
        )
        extractor._llm = Mock()
        extractor._llm.chat.completions.create.return_value = Mock(
            choices=[
                Mock(message=Mock(content='{"artists": [], "venue": "", "date": null}'))
            ]
        )

        with pytest.raises(ValueError, match="Could not extract artists, venue, date"):
            extractor.extract_show("https://example.com/event")
