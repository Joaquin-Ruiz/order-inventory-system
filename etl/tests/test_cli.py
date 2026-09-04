"""Regression tests for scheduler-facing CLI behavior."""

import shutil

import etl as pipeline


def test_renamed_workbook_is_detected_and_processed(
    orders_path, tmp_path, monkeypatch
):
    renamed = tmp_path / "incoming-export.xlsx"
    shutil.copy2(orders_path, renamed)
    pipeline._infer_source_kind.cache_clear()
    monkeypatch.setattr(
        pipeline,
        "load_settings",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run loaded credentials")),
    )

    assert pipeline.main(["--input", str(renamed), "--dry-run"]) == 0


def test_database_write_failure_returns_nonzero(monkeypatch):
    class _Connection:
        def close(self):
            pass

    monkeypatch.setattr(
        pipeline,
        "load_settings",
        lambda: pipeline.Settings(database_url="postgresql://test"),
    )
    monkeypatch.setattr(pipeline.repo, "create_connection", lambda _settings: _Connection())
    monkeypatch.setattr(
        pipeline,
        "_locate_file",
        lambda _folder, _inputs, kind: f"{kind}.xlsx",
    )
    monkeypatch.setattr(
        pipeline,
        "_run_one",
        lambda kind, path, name_to_sku, conn, dry_run, strict: pipeline.JobResult(
            kind=kind, path=path, raw=1, cleaned=1, written=-1
        ),
    )

    assert pipeline.main(["orders"]) == 1
