"""Adapters for repeatable tabular continuous-data sources.

The continuous CE 2.0 bridge needs to read its input twice: once to fit a
frozen encoder and once to count transitions.  CSV and Parquet paths can be
re-opened for each pass, while a Pandas or Polars DataFrame is already owned by
the caller.  This module makes that distinction explicit instead of pretending
that an in-memory frame has the same bounded-memory properties as a file.

Optional dataframe libraries are deliberately imported lazily.  Installing the
core package does not require Pandas, Polars, or PyArrow.
"""

from __future__ import annotations

import csv
import gzip
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


Row = Mapping[str, Any]


class TabularSource:
    """A repeatable source of named tabular rows for continuous analysis."""

    def iter_rows(self, columns: Sequence[str]) -> Iterator[Row]:
        """Yield the requested columns without materializing the full source."""
        raise NotImplementedError

    def column_names(self) -> list[str]:
        """Return the source's column names."""
        raise NotImplementedError

    def source_signature(self) -> dict[str, Any]:
        """Return a lightweight pass-to-pass source identity signature."""
        raise NotImplementedError

    def descriptor(self) -> dict[str, Any]:
        """Return JSON-safe source and memory-semantics metadata."""
        raise NotImplementedError

    def location_label(self, row_index: int) -> str:
        """Return a human-readable location for a zero-based row index."""
        return f"row {row_index + 1}"


@dataclass(frozen=True)
class CsvTabularSource(TabularSource):
    """A repeatable, bounded-memory CSV or CSV.GZ path source."""

    path: Path

    def iter_rows(self, columns: Sequence[str]) -> Iterator[Row]:
        requested = _normalize_requested_columns(columns)
        with _open_csv(self.path) as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV must include a header row.")
            _assert_columns_present(requested, reader.fieldnames, "CSV")
            yield from reader

    def column_names(self) -> list[str]:
        with _open_csv(self.path) as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError("CSV must include a header row.") from exc
        _validate_source_columns(header, "CSV")
        return header

    def source_signature(self) -> dict[str, Any]:
        return _file_signature(self.path)

    def descriptor(self) -> dict[str, Any]:
        return {
            "adapter": "csv_path",
            "format": "csv",
            "bounded_memory": True,
            "memory_semantics": "streaming_two_pass",
            "reopenable": True,
            "source_signature_policy": "file_size_and_modified_time",
            "compressed": self.path.suffix.lower() == ".gz",
        }

    def location_label(self, row_index: int) -> str:
        return f"CSV line {row_index + 2}"


@dataclass(frozen=True)
class ParquetTabularSource(TabularSource):
    """A bounded-memory Parquet path source backed by PyArrow batches."""

    path: Path
    batch_size: int = 65_536

    def iter_rows(self, columns: Sequence[str]) -> Iterator[Row]:
        requested = _normalize_requested_columns(columns)
        parquet_file = self._open_parquet()
        _assert_columns_present(requested, parquet_file.schema.names, "Parquet")
        for batch in parquet_file.iter_batches(batch_size=self.batch_size, columns=requested):
            arrays = batch.to_pydict()
            for values in zip(*(arrays[column] for column in requested)):
                yield dict(zip(requested, values))

    def column_names(self) -> list[str]:
        names = list(self._open_parquet().schema.names)
        _validate_source_columns(names, "Parquet")
        return names

    def source_signature(self) -> dict[str, Any]:
        return _file_signature(self.path)

    def descriptor(self) -> dict[str, Any]:
        return {
            "adapter": "parquet_path",
            "format": "parquet",
            "bounded_memory": True,
            "memory_semantics": "streaming_two_pass_arrow_batches",
            "reopenable": True,
            "source_signature_policy": "file_size_and_modified_time",
            "batch_size": self.batch_size,
        }

    def location_label(self, row_index: int) -> str:
        return f"Parquet row {row_index + 1}"

    def _open_parquet(self):
        if not self.path.is_file():
            raise FileNotFoundError(f"Parquet file not found: {self.path}")
        try:
            import pyarrow.parquet as parquet  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Reading Parquet paths requires the optional 'pyarrow' dependency. "
                "Install pyarrow or pass a Pandas/Polars DataFrame instead."
            ) from exc
        return parquet.ParquetFile(self.path)


@dataclass
class PandasDataFrameSource(TabularSource):
    """A caller-materialized Pandas DataFrame source."""

    frame: Any

    def iter_rows(self, columns: Sequence[str]) -> Iterator[Row]:
        requested = _normalize_requested_columns(columns)
        names = self.column_names()
        _assert_columns_present(requested, names, "Pandas DataFrame")
        series = [self.frame[column] for column in requested]
        for values in zip(*series):
            yield dict(zip(requested, values))

    def column_names(self) -> list[str]:
        names = list(self.frame.columns)
        _validate_source_columns(names, "Pandas DataFrame")
        return names

    def source_signature(self) -> dict[str, Any]:
        return {
            "kind": "pandas_dataframe",
            "object_id": id(self.frame),
            "row_count": int(len(self.frame)),
            "columns": self.column_names(),
            "dtypes": [str(dtype) for dtype in self.frame.dtypes],
        }

    def descriptor(self) -> dict[str, Any]:
        return {
            "adapter": "pandas_dataframe",
            "format": "dataframe",
            "bounded_memory": False,
            "memory_semantics": "caller_materialized_dataframe",
            "reopenable": True,
            "source_signature_policy": "object_identity_shape_columns_and_dtypes",
            "content_stability": "caller_responsibility_for_in_place_mutation",
        }

    def location_label(self, row_index: int) -> str:
        return f"Pandas DataFrame row {row_index + 1}"


@dataclass
class PolarsDataFrameSource(TabularSource):
    """A caller-materialized Polars DataFrame source."""

    frame: Any

    def iter_rows(self, columns: Sequence[str]) -> Iterator[Row]:
        requested = _normalize_requested_columns(columns)
        names = self.column_names()
        _assert_columns_present(requested, names, "Polars DataFrame")
        for values in self.frame.select(requested).iter_rows(named=False):
            yield dict(zip(requested, values))

    def column_names(self) -> list[str]:
        names = list(self.frame.columns)
        _validate_source_columns(names, "Polars DataFrame")
        return names

    def source_signature(self) -> dict[str, Any]:
        schema = self.frame.schema
        names = self.column_names()
        return {
            "kind": "polars_dataframe",
            "object_id": id(self.frame),
            "row_count": int(self.frame.height),
            "columns": names,
            "dtypes": [str(schema[name]) for name in names],
        }

    def descriptor(self) -> dict[str, Any]:
        return {
            "adapter": "polars_dataframe",
            "format": "dataframe",
            "bounded_memory": False,
            "memory_semantics": "caller_materialized_dataframe",
            "reopenable": True,
            "source_signature_policy": "object_identity_shape_columns_and_dtypes",
            "content_stability": "polars_dataframes_are_immutable; caller_controls_rebinding",
        }

    def location_label(self, row_index: int) -> str:
        return f"Polars DataFrame row {row_index + 1}"


def adapt_continuous_source(source: Any) -> TabularSource:
    """Normalize a CSV/Parquet path or Pandas/Polars DataFrame.

    File paths are repeatable and streamed.  In-memory DataFrames are accepted
    for convenience, but the caller has already paid their memory cost; their
    descriptor therefore reports ``bounded_memory: false``.
    """
    if isinstance(source, TabularSource):
        return source
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        if path.suffix.lower() in {".parquet", ".pq"}:
            return ParquetTabularSource(path)
        return CsvTabularSource(path)

    module = type(source).__module__
    class_name = type(source).__name__
    if class_name == "DataFrame" and module.startswith("pandas"):
        return PandasDataFrameSource(source)
    if class_name == "DataFrame" and module.startswith("polars"):
        return PolarsDataFrameSource(source)
    if class_name == "LazyFrame" and module.startswith("polars"):
        raise TypeError(
            "Polars LazyFrame is not accepted as a materialized DataFrame source. "
            "Collect it explicitly or pass a Parquet path for bounded streaming."
        )
    raise TypeError(
        "Continuous sources must be a CSV/Parquet path, Pandas DataFrame, "
        "Polars DataFrame, or TabularSource adapter."
    )


def describe_continuous_source(source: Any) -> dict[str, Any]:
    """Return JSON-safe source-adapter metadata without reading all rows."""
    return adapt_continuous_source(source).descriptor()


def _open_csv(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _file_signature(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Source file not found: {path}")
    stat = path.stat()
    return {"size_bytes": stat.st_size, "modified_time_ns": stat.st_mtime_ns}


def _normalize_requested_columns(columns: Sequence[str]) -> list[str]:
    requested: list[str] = []
    for column in columns:
        if not isinstance(column, str) or not column:
            raise ValueError("requested column names must be non-empty strings.")
        if column not in requested:
            requested.append(column)
    return requested


def _validate_source_columns(columns: Sequence[Any], context: str) -> None:
    if not columns:
        raise ValueError(f"{context} must include column names.")
    if any(not isinstance(column, str) or not column for column in columns):
        raise ValueError(f"{context} columns must be non-empty strings.")
    if len(set(columns)) != len(columns):
        raise ValueError(f"{context} columns must be unique.")


def _assert_columns_present(requested: Sequence[str], available: Sequence[Any], context: str) -> None:
    _validate_source_columns(available, context)
    missing = [column for column in requested if column not in available]
    if missing:
        raise ValueError(f"{context} is missing required column(s): {', '.join(missing)}.")
