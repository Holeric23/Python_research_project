import hashlib
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


DEFAULT_QUERIES_DIR = Path(__file__).with_name("queries")

_QUERY_PATTERN = re.compile(
    r"^--\s*name:\s*(?P<name>[a-zA-Z0-9_]+)\s*$",
    re.MULTILINE,
)


class DatabaseManager:
    """Application-level access to the project's SQLite database."""

    def __init__(
        self,
        database_path: str | Path,
        queries_dir: str | Path = DEFAULT_QUERIES_DIR,
    ) -> None:
        self._connection = sqlite3.connect(database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.row_factory = sqlite3.Row

        self._queries_dir = Path(queries_dir)
        self._queries = self._load_queries()

    def __enter__(self) -> "DatabaseManager":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """
        Run operations in one transaction unless a transaction
        is already active.
        """
        owns_transaction = not self._connection.in_transaction

        if owns_transaction:
            self._connection.execute("BEGIN")

        try:
            yield
        except Exception:
            if owns_transaction and self._connection.in_transaction:
                self._connection.rollback()
            raise
        else:
            if owns_transaction and self._connection.in_transaction:
                self._connection.commit()

    def get_or_create_source_type(self, name: str) -> int:
        name = self._validate_required_string(name, "name")

        with self.transaction():
            cursor = self._connection.execute(
                self._queries["source_type"]["insert"],
                (name,),
            )

            if cursor.rowcount == 1:
                return int(cursor.lastrowid)

            row = self._connection.execute(
                self._queries["source_type"]["select"],
                (name,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "SourceType was neither created nor found"
                )

            return int(row["id"])

    def get_or_create_source(
        self,
        source_type_id: int,
        name: str,
    ) -> int:
        if (
            not isinstance(source_type_id, int)
            or isinstance(source_type_id, bool)
            or source_type_id <= 0
        ):
            raise ValueError(
                "source_type_id must be a positive integer"
            )

        name = self._validate_required_string(name, "name")

        with self.transaction():
            cursor = self._connection.execute(
                self._queries["source"]["insert"],
                (source_type_id, name),
            )

            if cursor.rowcount == 1:
                return int(cursor.lastrowid)

            row = self._connection.execute(
                self._queries["source"]["select"],
                (source_type_id, name),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Source was neither created nor found"
                )

            return int(row["id"])

    def get_or_create_content(self, text: str) -> int:
        text = self._validate_content_text(text)
        text_hash = self.calculate_text_hash(text)

        with self.transaction():
            cursor = self._connection.execute(
                self._queries["content"]["insert"],
                (text, text_hash),
            )

            if cursor.rowcount == 1:
                return int(cursor.lastrowid)

            row = self._connection.execute(
                self._queries["content"]["select"],
                (text_hash,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Content was neither created nor found"
                )

            return int(row["id"])

    def create_publication(
        self,
        content_id: int,
        source_id: int,
        url: str,
        published_at: datetime | None,
    ) -> bool:
        self._validate_positive_id(content_id, "content_id")
        self._validate_positive_id(source_id, "source_id")

        url = self._validate_required_string(url, "url")

        if published_at is not None and not isinstance(
            published_at,
            datetime,
        ):
            raise TypeError(
                "published_at must be datetime or None"
            )

        published_at_value = (
            published_at.isoformat()
            if published_at is not None
            else None
        )

        with self.transaction():
            cursor = self._connection.execute(
                self._queries["publication"]["insert"],
                (
                    content_id,
                    source_id,
                    url,
                    published_at_value,
                ),
            )

            return cursor.rowcount == 1

    @staticmethod
    def calculate_text_hash(text: str) -> str:
        """Calculate SHA-256 from the exact stored text."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    def close(self) -> None:
        if self._connection.in_transaction:
            self._connection.rollback()

        self._connection.close()

    def _load_queries(self) -> dict[str, dict[str, str]]:
        query_files = {
            "source_type": "source_type.sql",
            "source": "source.sql",
            "content": "content.sql",
            "publication": "publication.sql",
        }

        queries: dict[str, dict[str, str]] = {}

        for key, filename in query_files.items():
            path = self._queries_dir / filename

            content = path.read_text(encoding="utf-8")

            matches = list(
                _QUERY_PATTERN.finditer(content)
            )

            if not matches:
                raise ValueError(
                    f"No named SQL queries found in {path}"
                )

            file_queries: dict[str, str] = {}

            for index, match in enumerate(matches):
                start = match.end()

                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(content)
                )

                sql = content[start:end].strip()

                if not sql:
                    raise ValueError(
                        f"Empty SQL query "
                        f"'{match.group('name')}' in {path}"
                    )

                file_queries[match.group("name")] = sql

            queries[key] = file_queries

        return queries

    @staticmethod
    def _validate_required_string(
        value: str,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{field_name} must be a string"
            )

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be empty"
            )

        return value

    @classmethod
    def _validate_content_text(cls, text: str) -> str:
        return cls._validate_required_string(
            text,
            "text",
        )

    @staticmethod
    def _validate_positive_id(
        value: int,
        field_name: str,
    ) -> None:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
        ):
            raise ValueError(
                f"{field_name} must be a positive integer"
            )