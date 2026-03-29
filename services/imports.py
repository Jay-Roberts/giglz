"""
Import service — CSV parsing and batch import logic.
"""

from dataclasses import dataclass, field, asdict
from datetime import date
from dateutil import parser as dateparser
import csv
import io

from db_models import db, ImportBatch, ImportRecord, ImportStatus, ImportSourceType, ShowSource
from services.shows import ShowService, DuplicateShowError


@dataclass
class ParsedCSVRow:
    artists: list[str]
    venue: str
    city: str
    date: date
    ticket_url: str | None

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dict for storage."""
        return {
            "artists": self.artists,
            "venue": self.venue,
            "city": self.city,
            "date": self.date.isoformat(),
            "ticket_url": self.ticket_url,
        }


@dataclass
class ImportResult:
    success: int = 0
    failed: int = 0
    skipped: int = 0
    not_found_artists: list[str] = field(default_factory=list)


class ImportService:
    def __init__(self):
        self.show_service = ShowService()

    def import_csv(self, user_id: str, file) -> ImportResult:
        """Parse CSV and import shows, tracking each row."""
        batch = ImportBatch(user_id=user_id)
        db.session.add(batch)
        db.session.flush()

        result = ImportResult()
        rows = self._parse_csv(file)

        for row in rows:
            record = ImportRecord(
                batch_id=batch.id,
                source_type=ImportSourceType.CSV_STRUCTURED,
                input_data=row.to_json_dict(),
                status=ImportStatus.PENDING,
            )
            db.session.add(record)
            db.session.flush()

            try:
                show, not_found = self._create_show(row)
                record.status = ImportStatus.SUCCESS
                record.show_id = show.id
                result.success += 1
                result.not_found_artists.extend(not_found)
            except DuplicateShowError:
                record.status = ImportStatus.SKIPPED
                record.error = "Duplicate show"
                result.skipped += 1
            except Exception as e:
                record.status = ImportStatus.FAILED
                record.error = str(e)
                result.failed += 1

        db.session.commit()
        return result

    def _parse_csv(self, file) -> list[ParsedCSVRow]:
        """Parse CSV, return list of parsed rows."""
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        reader = csv.DictReader(io.StringIO(content))
        rows = []

        for row in reader:
            # Skip empty rows
            if not row.get("artists") or not row.get("venue") or not row.get("date"):
                continue

            # Parse artists (comma-separated)
            artists = [a.strip() for a in row["artists"].split(",") if a.strip()]

            # Parse date with dateutil
            try:
                parsed_date = dateparser.parse(row["date"]).date()
            except (ValueError, TypeError, AttributeError):
                continue  # Skip unparseable dates

            rows.append(ParsedCSVRow(
                artists=artists,
                venue=row["venue"].strip(),
                city=row.get("city", "").strip(),
                date=parsed_date,
                ticket_url=row.get("ticket_url", "").strip() or None,
            ))

        return rows

    def _create_show(self, row: ParsedCSVRow) -> tuple:
        """Create show from parsed row. Returns (show, not_found_artists)."""
        show = self.show_service.add_show(
            artist_names=row.artists,
            show_date=row.date,
            venue_name=row.venue,
            city_name=row.city,
            ticket_url=row.ticket_url,
            source=ShowSource.CSV,
        )

        # Check which artists weren't found on Spotify
        not_found = [
            artist.name for artist in show.artists
            if not artist.spotify_id
        ]

        return show, not_found
