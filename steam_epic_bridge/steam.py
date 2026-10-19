from __future__ import annotations

import binascii
import shutil
from pathlib import Path

import psutil
import vdf

from steam_epic_bridge.config import (
    APP_ID_PREFIX,
    SHORTCUT_TAG,
    Settings,
    discover_environment,
    find_epic_launcher_binaries,
    find_legendary_binaries,
    find_steam_roots,
    find_steam_user_ids,
)
from steam_epic_bridge.launcher import build_shortcut_command
from steam_epic_bridge.models import EpicGame

__all__ = [
    "SteamShortcutsError",
    "is_steam_running",
    "compute_appid",
    "stable_unsigned_appid",
    "ensure_shortcuts_file",
    "backup_shortcuts",
    "latest_backup_path",
    "restore_shortcuts_backup",
    "sync_shortcuts",
    "add_games",
    "plan_add_games",
    "remove_epic_shortcuts",
    "existing_shortcuts_count",
    "clear_only_artwork",
    "sync_shortcut_icons",
    "discover_environment",
    "find_steam_roots",
    "find_steam_user_ids",
    "find_legendary_binaries",
    "find_epic_launcher_binaries",
]


class SteamShortcutsError(RuntimeError):
    pass


def is_steam_running() -> bool:
    """Verifica se o processo do cliente Steam está em execução."""
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name in ("steam.exe", "steam"):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_shortcuts(path: Path) -> dict:
    """Lê o shortcuts.vdf. Arquivo ausente ou vazio vira biblioteca vazia.

    Um arquivo que existe mas não pode ser lido NÃO é tratado como vazio: gravar por cima
    apagaria os atalhos não-Epic do usuário. Nesse caso levanta SteamShortcutsError.
    """
    if not path.exists() or path.stat().st_size == 0:
        return {"shortcuts": {}}
    try:
        with path.open("rb") as handle:
            payload = vdf.binary_load(handle)
    except Exception as exc:
        raise SteamShortcutsError(
            f"Nao foi possivel ler {path} (arquivo corrompido ou em formato inesperado). "
            "Nada foi alterado. Se houver um backup (.vdf.bak), use 'restore'."
        ) from exc
    return payload or {"shortcuts": {}}


def _save_shortcuts(path: Path, payload: dict) -> None:
    _ensure_parent(path)
    with path.open("wb") as handle:
        vdf.binary_dump(payload, handle)


def backup_shortcuts(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_suffix(".vdf.bak")
    shutil.copy2(path, backup)
    return backup


def latest_backup_path(path: Path) -> Path:
    return path.with_suffix(".vdf.bak")


def restore_shortcuts_backup(settings: Settings) -> Path:
    path = ensure_shortcuts_file(settings)
    backup = latest_backup_path(path)
    if not backup.exists():
        raise SteamShortcutsError("Nenhum backup de shortcuts.vdf foi encontrado para restauracao.")
    shutil.copy2(backup, path)
    return backup


def _iter_entries(payload: dict) -> list[tuple[str, dict]]:
    shortcuts = payload.setdefault("shortcuts", {})
    return [(str(key), value) for key, value in shortcuts.items() if str(key).isdigit()]


def _next_index(payload: dict) -> str:
    existing = [int(key) for key, _ in _iter_entries(payload)]
    return str(max(existing, default=-1) + 1)


def _shortcut_id(game: EpicGame | str) -> str:
    app_name = game.app_name if isinstance(game, EpicGame) else str(game)
    return f"{APP_ID_PREFIX}{app_name}"


def stable_unsigned_appid(game: EpicGame | str) -> int:
    """Gera unsigned int32 estável baseado exclusivamente em 'epic-<app_name>' (bit 31 setado)."""
    tag_id = _shortcut_id(game)
    return binascii.crc32(tag_id.encode("utf-8")) | 0x80000000


def compute_appid(settings: Settings | None, game: EpicGame | str) -> int:
    """Retorna o appid signed int32 estável gravado no shortcuts.vdf."""
    unsigned = stable_unsigned_appid(game)
    return unsigned if unsigned <= 0x7FFFFFFF else unsigned - 0x100000000


def _find_icon_in_grid(settings: Settings, unsigned_appid: int) -> str:
    if not settings.grid_dir or not settings.grid_dir.exists():
        return ""
    for ext in (".ico", ".png", ".jpg", ".jpeg"):
        candidate = settings.grid_dir / f"{unsigned_appid}_icon{ext}"
        if candidate.exists():
            return str(candidate)
    return ""


def _build_exe_and_launch(settings: Settings, game: EpicGame) -> tuple[str, str, str]:
    return build_shortcut_command(settings, game)


def _entry_for_game(settings: Settings, game: EpicGame) -> dict:
    exe, launch_opts, start_dir = _build_exe_and_launch(settings, game)
    signed_appid = compute_appid(settings, game)
    unsigned_appid = signed_appid & 0xFFFFFFFF
    shortcut_tag_id = _shortcut_id(game)

    return {
        "appid": signed_appid,
        "appname": game.title,
        "exe": exe,
        "StartDir": start_dir,
        "icon": _find_icon_in_grid(settings, unsigned_appid),
        "ShortcutPath": "",
        "LaunchOptions": launch_opts,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": shortcut_tag_id,
        "LastPlayTime": 0,
        "FlatpakAppID": "",
        "tags": {"0": SHORTCUT_TAG, "1": shortcut_tag_id},
    }


def ensure_shortcuts_file(settings: Settings) -> Path:
    if not settings.shortcuts_path:
        raise SteamShortcutsError("Nao foi possivel localizar a pasta userdata/config do Steam.")
    _ensure_parent(settings.shortcuts_path)
    if not settings.shortcuts_path.exists():
        _save_shortcuts(settings.shortcuts_path, {"shortcuts": {}})
    return settings.shortcuts_path


def _find_existing_entry(payload: dict, game: EpicGame) -> dict | None:
    """Busca atalho existente pela tag 'epic-<app_name>' ou DevkitGameID.

    Como último recurso, reaproveita um atalho antigo do próprio app (que tem a tag
    SHORTCUT_TAG mas ainda não tem o identificador estável) com o mesmo título.
    Atalhos criados à mão pelo usuário nunca são reivindicados só pelo nome.
    """
    target_tag = _shortcut_id(game)
    target_title = game.title.casefold()

    for _, entry in _iter_entries(payload):
        tags = {str(v) for v in entry.get("tags", {}).values()}
        if target_tag in tags or entry.get("DevkitGameID") == target_tag:
            return entry

    for _, entry in _iter_entries(payload):
        tags = {str(v) for v in entry.get("tags", {}).values()}
        is_legacy_bridge_entry = SHORTCUT_TAG in tags and not any(
            t.startswith(APP_ID_PREFIX) for t in tags
        )
        if is_legacy_bridge_entry and str(entry.get("appname", "")).casefold() == target_title:
            return entry

    return None


def _migrate_grid_files(grid_dir: Path | None, old_appid: int, new_appid: int) -> None:
    """Migra as artes já baixadas no disco quando um atalho antigo muda para o appid estável."""
    if not grid_dir or not grid_dir.exists() or not old_appid or old_appid == new_appid:
        return
    old_u = old_appid & 0xFFFFFFFF
    new_u = new_appid & 0xFFFFFFFF
    for suffix in ("p", "_hero", "_logo", "_icon"):
        for ext in (".png", ".jpg", ".jpeg", ".ico", ".webp"):
            old_file = grid_dir / f"{old_u}{suffix}{ext}"
            new_file = grid_dir / f"{new_u}{suffix}{ext}"
            if old_file.exists():
                try:
                    if not new_file.exists():
                        old_file.rename(new_file)
                    else:
                        old_file.unlink()
                except OSError:
                    pass


def sync_shortcuts(
    settings: Settings,
    games: list[EpicGame],
) -> tuple[int, int, int, Path | None]:
    """Cria atalhos novos e corrige os existentes em uma única operação idempotente.
    Retorna (created, updated, skipped, backup_path).
    """
    from steam_epic_bridge.artwork import ensure_game_icon

    path = ensure_shortcuts_file(settings)
    payload = _load_shortcuts(path)
    backup = backup_shortcuts(path)

    created = 0
    updated = 0
    skipped = 0

    for game in games:
        desired = _entry_for_game(settings, game)
        existing = _find_existing_entry(payload, game)
        new_appid = int(desired["appid"])
        unsigned_new = new_appid & 0xFFFFFFFF

        if existing is None:
            ensure_game_icon(settings.grid_dir, new_appid)
            desired["icon"] = _find_icon_in_grid(settings, unsigned_new)
            payload["shortcuts"][_next_index(payload)] = desired
            created += 1
            continue

        old_appid = int(existing.get("appid", 0))
        if old_appid and old_appid != new_appid:
            _migrate_grid_files(settings.grid_dir, old_appid, new_appid)

        ensure_game_icon(settings.grid_dir, new_appid)
        desired["icon"] = _find_icon_in_grid(settings, unsigned_new)

        changed = False
        for field_name in ("appid", "appname", "exe", "StartDir", "LaunchOptions", "DevkitGameID", "tags"):
            if existing.get(field_name) != desired.get(field_name):
                existing[field_name] = desired[field_name]
                changed = True

        if desired["icon"] and existing.get("icon") != desired["icon"]:
            existing["icon"] = desired["icon"]
            changed = True

        if changed:
            updated += 1
        else:
            skipped += 1

    _save_shortcuts(path, payload)
    return created, updated, skipped, backup


def add_games(settings: Settings, games: list[EpicGame]) -> tuple[int, int, Path | None]:
    """Wrapper compatível que retorna (created, skipped, backup_path)."""
    created, updated, skipped, backup = sync_shortcuts(settings, games)
    return created, skipped + updated, backup


def plan_add_games(settings: Settings, games: list[EpicGame]) -> tuple[int, int]:
    """Dry-run sem efeitos colaterais: retorna (planned_created, existing_count)."""
    path = settings.shortcuts_path
    payload = _load_shortcuts(path) if path and path.exists() else {"shortcuts": {}}
    created = 0
    skipped = 0

    for game in games:
        if _find_existing_entry(payload, game) is not None:
            skipped += 1
        else:
            created += 1

    return created, skipped


def sync_shortcut_icons(settings: Settings) -> int:
    """Garante que todo atalho Epic tenha um _icon.ico válido (gerando da capa se faltar)
    e vincula ao campo 'icon' do shortcuts.vdf para eliminar o ícone de pasta amarela do explorer.exe.
    """
    from steam_epic_bridge.artwork import ensure_game_icon

    if not settings.shortcuts_path or not settings.shortcuts_path.exists():
        return 0
    if not settings.grid_dir or not settings.grid_dir.exists():
        return 0

    payload = _load_shortcuts(settings.shortcuts_path)
    updated = 0
    for _, entry in _iter_entries(payload):
        tags = {str(v) for v in entry.get("tags", {}).values()}
        if SHORTCUT_TAG not in tags:
            continue
        appid = int(entry.get("appid", 0))
        if not appid:
            continue
        unsigned_appid = appid & 0xFFFFFFFF
        ensure_game_icon(settings.grid_dir, appid)
        found_icon = _find_icon_in_grid(settings, unsigned_appid)
        if found_icon and entry.get("icon") != found_icon:
            entry["icon"] = found_icon
            updated += 1

    if updated > 0:
        _save_shortcuts(settings.shortcuts_path, payload)
    return updated


def _remove_grid_images_for_appid(grid_dir: Path | None, appid: int) -> int:
    if not appid or not grid_dir or not grid_dir.exists():
        return 0
    removed = 0
    unsigned_appid = appid & 0xFFFFFFFF
    for suffix in ("p", "_hero", "_logo", "_icon"):
        for ext in (".png", ".jpg", ".jpeg", ".ico", ".webp"):
            img_path = grid_dir / f"{unsigned_appid}{suffix}{ext}"
            try:
                if img_path.exists():
                    img_path.unlink()
                    removed += 1
            except OSError:
                pass
    return removed


def remove_epic_shortcuts(settings: Settings) -> int:
    path = ensure_shortcuts_file(settings)
    payload = _load_shortcuts(path)
    filtered: dict[str, dict] = {}
    removed = 0

    for _, entry in _iter_entries(payload):
        tags = {str(v) for v in entry.get("tags", {}).values()}
        if SHORTCUT_TAG in tags:
            removed += 1
            _remove_grid_images_for_appid(settings.grid_dir, int(entry.get("appid", 0)))
            continue
        filtered[str(len(filtered))] = entry

    if removed:
        backup_shortcuts(path)
        payload["shortcuts"] = filtered
        _save_shortcuts(path, payload)
    return removed


def existing_shortcuts_count(settings: Settings) -> int:
    if not settings.shortcuts_path or not settings.shortcuts_path.exists():
        return 0
    payload = _load_shortcuts(settings.shortcuts_path)
    return sum(
        1
        for _, entry in _iter_entries(payload)
        if SHORTCUT_TAG in {str(v) for v in entry.get("tags", {}).values()}
    )


def clear_only_artwork(settings: Settings) -> int:
    path = ensure_shortcuts_file(settings)
    payload = _load_shortcuts(path)
    removed_files = 0
    for _, entry in _iter_entries(payload):
        tags = {str(v) for v in entry.get("tags", {}).values()}
        if SHORTCUT_TAG in tags:
            removed_files += _remove_grid_images_for_appid(settings.grid_dir, int(entry.get("appid", 0)))
    return removed_files
