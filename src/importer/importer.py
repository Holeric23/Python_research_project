import logging
import sqlite3
from dataclasses import dataclass, field

from src.database import DatabaseManager
from src.parsers import Parser
from src.utils.dataclasses import RawPublication


logger = logging.getLogger(__name__)


@dataclass
class ImportError:
    url: str
    error_type: str
    error_message: str


@dataclass
class ImportReport:
    processed: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[ImportError] = field(
        default_factory=list
    )


class Importer:
    """Coordinates parser execution and publication import."""

    def __init__(
        self,
        database_manager: DatabaseManager,
    ) -> None:
        self._database_manager = database_manager

    async def import_from(
        self,
        parser: Parser,
    ) -> ImportReport:
        publications = await parser.parse()

        report = ImportReport()

        for publication in publications:
            report.processed += 1

            try:
                created = self._import_publication(
                    publication
                )

                if created:
                    report.created += 1
                else:
                    report.skipped += 1

            except sqlite3.OperationalError:
                raise

            except sqlite3.DatabaseError as error:
                report.failed += 1
                self._add_error(
                    report,
                    publication,
                    error,
                )

            except Exception as error:
                report.failed += 1
                self._add_error(
                    report,
                    publication,
                    error,
                )

        return report

    def _import_publication(
        self,
        publication: RawPublication,
    ) -> bool:
        with self._database_manager.transaction():
            source_type_id = (
                self._database_manager
                .get_or_create_source_type(
                    publication.source_type_name
                )
            )

            source_id = (
                self._database_manager
                .get_or_create_source(
                    source_type_id,
                    publication.source_name,
                )
            )

            content_id = (
                self._database_manager
                .get_or_create_content(
                    publication.text
                )
            )

            return (
                self._database_manager
                .create_publication(
                    content_id,
                    source_id,
                    publication.url,
                    publication.published_at,
                )
            )

    @staticmethod
    def _add_error(
        report: ImportReport,
        publication: RawPublication,
        error: Exception,
    ) -> None:
        error_info = ImportError(
            url=publication.url,
            error_type=type(error).__name__,
            error_message=str(error),
        )

        report.errors.append(error_info)

        logger.exception(
            "Failed to import publication: %s",
            publication.url,
        )