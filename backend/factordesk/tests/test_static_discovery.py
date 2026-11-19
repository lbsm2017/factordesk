"""Where ``serve`` finds the built page: a checkout's frontend/dist or the folder in a wheel."""

from __future__ import annotations

from pathlib import Path

import pytest
import uvicorn

from factordesk import cli
from factordesk.api import deps


def _fake_web(root: Path, title: str) -> Path:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(f"<!doctype html><title>{title}</title>", encoding="utf-8")
    return root


def test_checkout_dist_wins_when_both_exist(tmp_path: Path) -> None:
    dist = _fake_web(tmp_path / "dist", "dist")
    packaged = _fake_web(tmp_path / "web", "packaged")
    assert cli.resolve_static_dir(dist, packaged) == dist


def test_packaged_folder_is_used_when_there_is_no_checkout_build(tmp_path: Path) -> None:
    packaged = _fake_web(tmp_path / "web", "packaged")
    assert cli.resolve_static_dir(tmp_path / "no-dist", packaged) == packaged


def test_neither_present_names_the_checkout_folder_to_build(tmp_path: Path) -> None:
    dist = tmp_path / "no-dist"
    assert cli.resolve_static_dir(dist, tmp_path / "no-web") == dist


def test_a_folder_without_index_html_does_not_count(tmp_path: Path) -> None:
    empty = tmp_path / "dist"
    (empty / "assets").mkdir(parents=True)
    packaged = _fake_web(tmp_path / "web", "packaged")
    assert cli.resolve_static_dir(empty, packaged) == packaged


def test_module_constants_point_at_the_checkout_dist_and_the_package_web_folder() -> None:
    package = Path(cli.__file__).resolve().parent
    assert package / "web" == cli.PACKAGED_STATIC_DIR
    assert package.parents[1] / "frontend" / "dist" == cli.DEFAULT_STATIC_DIR


@pytest.fixture
def run_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_run(app: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)

    def no_preload(host: str, port: int) -> None:
        return None

    monkeypatch.setattr(cli, "_preload_when_ready", no_preload)
    return calls


def test_serve_from_a_wheel_layout_uses_the_packaged_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, object]]
) -> None:
    packaged = _fake_web(tmp_path / "web", "packaged")
    monkeypatch.setattr(cli, "DEFAULT_STATIC_DIR", tmp_path / "no-dist")
    monkeypatch.setattr(cli, "PACKAGED_STATIC_DIR", packaged)
    seen: list[Path | None] = []
    real = deps.default_deps

    def spy(static_dir: Path | None = None) -> deps.AppDeps:
        seen.append(static_dir)
        return real(static_dir)

    monkeypatch.setattr(deps, "default_deps", spy)
    assert cli.main(["serve", "--port", "8765"]) == cli.EXIT_OK
    assert seen == [packaged]
    assert len(run_calls) == 1


def test_serve_static_option_still_overrides_the_packaged_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_calls: list[dict[str, object]]
) -> None:
    monkeypatch.setattr(cli, "PACKAGED_STATIC_DIR", _fake_web(tmp_path / "web", "packaged"))
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.main(["serve", "--static", str(empty), "--port", "8765"]) == cli.EXIT_USAGE
    assert run_calls == []


def test_serve_in_a_wheel_without_the_page_says_to_reinstall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_calls: list[dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_IN_CHECKOUT", False)
    monkeypatch.setattr(cli, "DEFAULT_STATIC_DIR", tmp_path / "no-dist")
    monkeypatch.setattr(cli, "PACKAGED_STATIC_DIR", tmp_path / "no-web")
    assert cli.main(["serve", "--port", "8765"]) == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "reinstall factordesk" in err
    assert "npm" not in err
    assert run_calls == []
