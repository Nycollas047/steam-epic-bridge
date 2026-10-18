from __future__ import annotations

import concurrent.futures
import json
import re
import time
from pathlib import Path
from typing import Callable

import requests

from steam_epic_bridge.config import Settings, _CONFIG_DIR
from steam_epic_bridge.models import EpicGame


class ArtworkError(RuntimeError):
    pass


# Convenção de nomes da Steam para atalhos na pasta userdata/<id>/config/grid/:
#   Grid  (poster vertical 600x900): {unsigned_appid}p.png
#   Hero  (banner 1920x620):         {unsigned_appid}_hero.png
#   Logo  (logo transparente):       {unsigned_appid}_logo.png
#   Icon  (ícone quadrado):          {unsigned_appid}_icon.png
IMAGE_TYPES: dict[str, tuple[str, str]] = {
    "grid": ("grids", "p"),
    "hero": ("heroes", "_hero"),
    "logo": ("logos", "_logo"),
    "icon": ("icons", "_icon"),
}

_EDITION_SUFFIXES = (
    "complete edition",
    "the complete edition",
    "game of the year edition",
    "goty edition",
    "ultimate edition",
    "definitive edition",
    "deluxe edition",
    "premium edition",
    "gold edition",
    "legendary edition",
    "special edition",
    "remastered",
    "collection",
)

_FAILED_SEARCH_FILE = _CONFIG_DIR / "failed_searches.json"


def _session(settings: Settings) -> requests.Session:
    if not settings.steamgriddb_api_key:
        raise ArtworkError("STEAMGRIDDB_API_KEY nao configurada.")
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {settings.steamgriddb_api_key}"
    session.headers["User-Agent"] = "steam-epic-bridge/0.2"
    return session


def build_steamgriddb_params(
    asset_type: str,
    style: str = "any",
    prefer_animated: bool = False,
) -> dict[str, str]:
    """Filtra a consulta na origem na API v2 do SteamGridDB (poster vertical, resolução e formato)."""
    params: dict[str, str] = {
        "nsfw": "false",
        "humor": "false",
        "types": "animated,static" if prefer_animated else "static",
    }

    if asset_type == "grid":
        params["dimensions"] = "600x900,660x930,342x482"
        params["mimes"] = "image/png,image/jpeg"
        valid_styles = {"alternate", "blurred", "white_logo", "material", "no_logo", "minimal"}
        if style in valid_styles:
            params["styles"] = style
    elif asset_type == "hero":
        params["dimensions"] = "1920x620,3840x1240"
        params["mimes"] = "image/png,image/jpeg"
    elif asset_type == "logo":
        params["mimes"] = "image/png"
    elif asset_type == "icon":
        # Não restringe dimensions em ícones para não descartar ícones 64x64/128x128/256x256 ou .ico nativos
        params.pop("types", None)

    return params


def ensure_ico_file(source: Path, destination: Path | None = None) -> Path | None:
    """Converte qualquer imagem (.png, .jpg, .ico) em um arquivo .ico quadrado (256x256, 64x64, 32x32)
    para que a barra lateral da Steam no Windows nunca mostre o ícone de pasta amarela do explorer.exe.
    """
    from PIL import Image

    if not source.exists():
        return None
    destination = destination or source.with_suffix(".ico")
    try:
        with Image.open(source) as img:
            img = img.convert("RGBA")
            w, h = img.size
            # Se a imagem não for quadrada (ex: fallback a partir de poster vertical), recorta o quadrado central
            if w != h:
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 4  # Prioriza o topo/centro onde costuma ficar a arte principal
                img = img.crop((left, top, left + side, top + side))
            img_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
            img_256.save(destination, format="ICO", sizes=[(256, 256), (64, 64), (32, 32)])
        return destination
    except Exception:
        return None


def ensure_game_icon(grid_dir: Path | None, appid: int) -> Path | None:
    """Garante que exista {unsigned_appid}_icon.ico na pasta grid, convertendo de _icon.png
    ou criando a partir do poster/logo caso o SteamGridDB não tenha ícone para o jogo.
    """
    if not grid_dir or not grid_dir.exists():
        return None
    unsigned_appid = appid & 0xFFFFFFFF
    ico_target = grid_dir / f"{unsigned_appid}_icon.ico"
    if ico_target.exists():
        return ico_target

    # 1. Tenta converter um _icon.png/.jpg existente
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = grid_dir / f"{unsigned_appid}_icon{ext}"
        if candidate.exists():
            res = ensure_ico_file(candidate, ico_target)
            if res and res.exists():
                return res

    # 2. Fallback: gera ícone quadrado a partir da capa vertical (p) ou logo (_logo)
    for suffix in ("p", "_logo"):
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = grid_dir / f"{unsigned_appid}{suffix}{ext}"
            if candidate.exists():
                res = ensure_ico_file(candidate, ico_target)
                if res and res.exists():
                    return res
    return None


def _candidate_search_terms(game: EpicGame) -> list[str]:
    raw_terms = [game.title.strip()]
    cleaned_terms: list[str] = []
    seen: set[str] = set()

    def add_term(term: str) -> None:
        normalized_key = term.casefold().strip()
        if not normalized_key or normalized_key in seen:
            return
        seen.add(normalized_key)
        cleaned_terms.append(term.strip())

    for term in raw_terms:
        add_term(term)
        flattened = re.sub(r"[:\-_/]+", " ", term).strip()
        add_term(flattened)

        for suffix in _EDITION_SUFFIXES:
            pattern = re.compile(rf"[\s:\-–—]*{re.escape(suffix)}$", re.IGNORECASE)
            shortened = pattern.sub("", term).strip(" :-–—")
            if shortened and shortened != term:
                add_term(shortened)
                add_term(re.sub(r"[:\-_/]+", " ", shortened).strip())

        if ":" in term:
            add_term(term.split(":", 1)[0].strip())
        if " - " in term:
            add_term(term.split(" - ", 1)[0].strip())

    return cleaned_terms


def _search_game_id(session: requests.Session, game: EpicGame) -> int | None:
    for term in _candidate_search_terms(game):
        response = session.get(
            "https://www.steamgriddb.com/api/v2/search/autocomplete/" + requests.utils.quote(term),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        if data:
            return data[0].get("id")
    return None


def _download_asset(
    session: requests.Session,
    endpoint: str,
    game_id: int,
    params: dict[str, str] | None = None,
) -> str | None:
    url = f"https://www.steamgriddb.com/api/v2/{endpoint}/game/{game_id}"
    response = session.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json().get("data") or []
    if not data and params:
        # Fallback sem filtro de estilo/dimensão estrita caso o jogo seja raro
        fallback_params = {"dimensions": params["dimensions"]} if "dimensions" in params else None
        response = session.get(url, params=fallback_params, timeout=20)
        response.raise_for_status()
        data = response.json().get("data") or []
    if not data:
        return None
    return data[0].get("url")


def _save_image(url: str, destination: Path) -> bool:
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "steam-epic-bridge/0.2"})
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return True
    except Exception:
        return False


def _load_failed_searches() -> dict:
    if not _FAILED_SEARCH_FILE.exists():
        return {}
    try:
        return json.loads(_FAILED_SEARCH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_failed_search(game_title: str) -> None:
    data = _load_failed_searches()
    data[game_title] = time.time()
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _FAILED_SEARCH_FILE.write_text(json.dumps(data), encoding="utf-8")


def _is_blacklisted(game_title: str) -> bool:
    last_fail = _load_failed_searches().get(game_title)
    if not last_fail:
        return False
    return (time.time() - last_fail) < (30 * 24 * 60 * 60)


def clear_artwork_cache() -> int:
    if _FAILED_SEARCH_FILE.exists():
        try:
            _FAILED_SEARCH_FILE.unlink()
            return 1
        except OSError:
            pass
    return 0


def has_vertical_cover(grid_dir: Path | None, appid: int) -> bool:
    if not grid_dir or not grid_dir.exists():
        return False
    unsigned_appid = appid & 0xFFFFFFFF
    return any((grid_dir / f"{unsigned_appid}p{ext}").exists() for ext in (".png", ".jpg", ".jpeg"))


def download_artwork_for_game(settings: Settings, game: EpicGame, appid: int) -> int:
    if not settings.grid_dir:
        raise ArtworkError("Diretorio grid do Steam nao encontrado.")

    unsigned_appid = appid & 0xFFFFFFFF
    missing_endpoints: list[tuple[str, str, str]] = []

    for suffix, (endpoint, steam_suffix) in IMAGE_TYPES.items():
        if not any(
            (settings.grid_dir / f"{unsigned_appid}{steam_suffix}{ext}").exists()
            for ext in (".png", ".jpg", ".jpeg", ".ico")
        ):
            missing_endpoints.append((suffix, endpoint, steam_suffix))

    if not missing_endpoints or _is_blacklisted(game.title):
        return 0

    session = _session(settings)
    try:
        game_id = _search_game_id(session, game)
    except Exception:
        return 0

    if not game_id:
        _save_failed_search(game.title)
        return 0

    downloaded = 0
    for suffix, endpoint, steam_suffix in missing_endpoints:
        params = build_steamgriddb_params(
            suffix,
            style=settings.artwork_style,
            prefer_animated=settings.prefer_animated,
        )
        try:
            image_url = _download_asset(session, endpoint, game_id, params=params)
        except Exception:
            continue
        if not image_url:
            continue

        ext = Path(image_url).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".ico"):
            ext = ".png"
        if suffix == "icon" and ext not in (".png", ".ico"):
            ext = ".png"

        destination = settings.grid_dir / f"{unsigned_appid}{steam_suffix}{ext}"
        if _save_image(image_url, destination):
            if suffix == "icon" and destination.suffix.lower() != ".ico":
                ensure_ico_file(destination, settings.grid_dir / f"{unsigned_appid}_icon.ico")
            downloaded += 1

    # Garante que todo jogo fique com _icon.ico (mesmo se não havia ícone dedicado no SteamGridDB)
    ensure_game_icon(settings.grid_dir, appid)
    return downloaded


def download_artwork_batch(
    settings: Settings,
    games_with_appid: list[tuple[EpicGame, int]],
    max_workers: int = 5,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> tuple[int, int]:
    """Baixa capas em paralelo. Retorna (total_arquivos_baixados, jogos_sem_capa_vertical)."""
    if not settings.grid_dir:
        return 0, len(games_with_appid)

    total_downloaded = 0
    total_games = len(games_with_appid)
    completed_count = 0

    def _task(game: EpicGame, appid: int) -> int:
        return download_artwork_for_game(settings, game, appid)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_game = {
            executor.submit(_task, game, appid): (game, appid)
            for game, appid in games_with_appid
        }
        for future in concurrent.futures.as_completed(future_to_game):
            completed_count += 1
            game, _ = future_to_game[future]
            if progress_callback:
                progress_callback(game.title, completed_count, total_games)
            try:
                total_downloaded += future.result()
            except Exception:
                pass

    missing_cover = sum(
        1 for _, appid in games_with_appid if not has_vertical_cover(settings.grid_dir, appid)
    )
    return total_downloaded, missing_cover
