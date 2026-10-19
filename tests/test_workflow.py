from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image
import pytest

from steam_epic_bridge.config import Settings
from steam_epic_bridge.models import DiscoveryResult, EpicGame


def _make_settings(tmp_path: Path) -> Settings:
    steam_root = tmp_path / "Steam"
    user_id = "12345678"
    (steam_root / "userdata" / user_id / "config" / "grid").mkdir(parents=True)
    return Settings(
        steam_root=steam_root,
        steam_user_id=user_id,
        legendary_bin="legendary",
        steamgriddb_api_key=None,
        debug=False,
        discovery=DiscoveryResult(),
    )


def _make_game(app_name: str = "Fortnite", title: str = "Fortnite", installed: bool = True) -> EpicGame:
    launch_command = (
        f'legendary launch "{app_name}"'
        if installed
        else f"com.epicgames.launcher://apps/{app_name}?action=launch&silent=true"
    )
    return EpicGame(
        app_name=app_name,
        title=title,
        launch_command=launch_command,
        is_installed=installed,
        install_path=r"C:\Games" if installed else None,
    )


class TestPlanningAndRestore:
    def test_plan_add_games_matches_expected(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import add_games, plan_add_games

        settings = _make_settings(tmp_path)
        add_games(settings, [_make_game("Fortnite", "Fortnite")])
        created, skipped = plan_add_games(
            settings,
            [_make_game("Fortnite", "Fortnite"), _make_game("RL", "Rocket League")],
        )
        assert created == 1
        assert skipped == 1

    def test_restore_backup_recovers_previous_file(self, tmp_path: Path) -> None:
        from steam_epic_bridge.steam import add_games, restore_shortcuts_backup

        settings = _make_settings(tmp_path)
        add_games(settings, [_make_game("Fortnite", "Fortnite")])
        assert settings.shortcuts_path is not None
        original_bytes = settings.shortcuts_path.read_bytes()

        add_games(settings, [_make_game("RL", "Rocket League")])
        changed_bytes = settings.shortcuts_path.read_bytes()
        assert changed_bytes != original_bytes

        backup = restore_shortcuts_backup(settings)
        restored_bytes = settings.shortcuts_path.read_bytes()

        assert backup.exists()
        assert restored_bytes == original_bytes


class TestDoctorAndUnifiedSync:
    def test_doctor_reports_backup_availability(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.cli import doctor

        settings = _make_settings(tmp_path)
        assert settings.shortcuts_path is not None
        settings.shortcuts_path.write_bytes(b"")
        settings.shortcuts_path.with_suffix(".vdf.bak").write_bytes(b"backup")

        monkeypatch.setattr("steam_epic_bridge.cli.ensure_authenticated", lambda settings: "EpicUser")
        monkeypatch.setattr("steam_epic_bridge.cli.list_games", lambda settings: [])

        result = doctor(settings)
        assert result["backup_available"] is True
        assert result["epic_authenticated"] is True
        assert result["epic_account"] == "EpicUser"
        assert result["epic_games"] == 0

    def test_sync_dry_run_does_not_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.cli import sync_library

        settings = _make_settings(tmp_path)
        assert settings.shortcuts_path is not None
        before = settings.shortcuts_path.read_bytes() if settings.shortcuts_path.exists() else None

        monkeypatch.setattr("steam_epic_bridge.cli.ensure_authenticated", lambda settings: "EpicUser")
        monkeypatch.setattr(
            "steam_epic_bridge.cli.list_games",
            lambda settings, **kwargs: [_make_game("Fortnite", "Fortnite"), _make_game("RL", "Rocket League")],
        )

        result = sync_library(settings, dry_run=True)
        after = settings.shortcuts_path.read_bytes() if settings.shortcuts_path.exists() else None

        assert result.planned == 2
        assert result.created == 0
        assert result.skipped == 0
        assert before == after

    def test_sync_installed_only_filters_uninstalled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.cli import sync_library

        settings = _make_settings(tmp_path)
        monkeypatch.setattr("steam_epic_bridge.cli.ensure_authenticated", lambda settings: "EpicUser")
        monkeypatch.setattr(
            "steam_epic_bridge.cli.list_games",
            lambda settings, **kwargs: [
                _make_game("Fortnite", "Fortnite", installed=True),
                _make_game("UEFN", "Unreal Editor", installed=False),
            ],
        )

        result = sync_library(settings, dry_run=True, installed_only=True)
        assert result.planned == 1

    def test_sync_idempotent_across_windows_and_linux(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from steam_epic_bridge.cli import sync_library

        for platform_name in ("win32", "linux"):
            monkeypatch.setattr(sys, "platform", platform_name)
            sub_dir = tmp_path / platform_name
            settings = _make_settings(sub_dir)
            games = [_make_game("Sugar", "Rocket League"), _make_game("Fn", "Fortnite", installed=False)]

            monkeypatch.setattr("steam_epic_bridge.cli.ensure_authenticated", lambda s: "EpicUser")
            monkeypatch.setattr("steam_epic_bridge.cli.list_games", lambda s, **kw: games)

            r1 = sync_library(settings, download_artwork=False)
            assert r1.created == 2
            assert r1.updated == 0
            assert r1.skipped == 0

            r2 = sync_library(settings, download_artwork=False)
            assert r2.created == 0
            assert r2.updated == 0
            assert r2.skipped == 2

    def test_sync_converts_and_links_ico_icon_to_vdf(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from steam_epic_bridge.steam import _load_shortcuts, add_games, compute_appid, sync_shortcut_icons

        settings = _make_settings(tmp_path)
        game = _make_game("Fortnite", "Fortnite")
        add_games(settings, [game])

        unsigned_appid = compute_appid(settings, game) & 0xFFFFFFFF
        assert settings.grid_dir is not None
        png_icon = settings.grid_dir / f"{unsigned_appid}_icon.png"
        with Image.new("RGBA", (64, 64), (255, 0, 0, 255)) as image:
            image.save(png_icon, format="PNG")

        updated = sync_shortcut_icons(settings)
        ico_icon = settings.grid_dir / f"{unsigned_appid}_icon.ico"
        assert updated == 1
        assert ico_icon.exists()
        assert settings.shortcuts_path is not None
        payload = _load_shortcuts(settings.shortcuts_path)
        assert payload["shortcuts"]["0"]["icon"] == str(ico_icon)

    def test_artwork_download_with_fake_api_responses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from steam_epic_bridge.artwork import download_artwork_for_game
        from steam_epic_bridge.steam import compute_appid

        settings = _make_settings(tmp_path)
        settings.steamgriddb_api_key = "fake-key-123"
        game = _make_game("Sugar", "Rocket League")
        appid = compute_appid(settings, game)
        unsigned = appid & 0xFFFFFFFF

        monkeypatch.setattr("steam_epic_bridge.artwork._search_game_id", lambda session, g: 999)
        monkeypatch.setattr(
            "steam_epic_bridge.artwork._download_asset",
            lambda session, endpoint, gid, params=None: f"https://cdn.example.com/{endpoint}.png",
        )

        def fake_save_image(url: str, destination: Path) -> bool:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"PNGDATA")
            return True

        monkeypatch.setattr("steam_epic_bridge.artwork._save_image", fake_save_image)

        downloaded = download_artwork_for_game(settings, game, appid)
        assert downloaded == 4
        assert settings.grid_dir is not None
        assert (settings.grid_dir / f"{unsigned}p.png").exists()
        assert (settings.grid_dir / f"{unsigned}_hero.png").exists()
        assert (settings.grid_dir / f"{unsigned}_logo.png").exists()
        assert (settings.grid_dir / f"{unsigned}_icon.png").exists()


class TestArtworkMatching:
    def test_candidate_search_terms_strip_common_edition_suffixes(self) -> None:
        from steam_epic_bridge.artwork import _candidate_search_terms

        game = _make_game("BioshockInfinite", "BioShock Infinite: Complete Edition")
        terms = _candidate_search_terms(game)

        assert "BioShock Infinite: Complete Edition" in terms
        assert "BioShock Infinite" in terms
