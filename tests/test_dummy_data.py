"""Tests for large shared dummy datasets used by demo-mode TUIs."""
from __future__ import annotations

from p5.dummy_data import (
    LARGE_DUMMY_DATASET_SIZE,
    build_change_files,
    build_changes_records,
    build_submit_cls,
    build_ws_records,
)


def test_changes_dummy_data_has_large_dataset():
    records = build_changes_records()

    assert len(records) >= LARGE_DUMMY_DATASET_SIZE
    assert records[0].cl == "123472"
    assert any("paging and filtering" in record.description for record in records)


def test_change_dummy_data_has_large_dataset():
    files = build_change_files()

    assert len(files) >= LARGE_DUMMY_DATASET_SIZE
    assert files[0].rel_path == "src/auth/login.cpp"
    assert any(file.rel_path.endswith("bulk_99.cpp") for file in files)


def test_submit_dummy_data_has_large_dataset():
    pending_cls = build_submit_cls()

    assert len(pending_cls) >= LARGE_DUMMY_DATASET_SIZE
    assert pending_cls[0].cl == "default"
    assert any(cl.cl == "123699" for cl in pending_cls)


def test_workspace_dummy_data_has_large_dataset():
    records = build_ws_records()

    assert len(records) >= LARGE_DUMMY_DATASET_SIZE
    assert records[0].name == "gigo-main"
    assert any(record.name.endswith("099") for record in records)
