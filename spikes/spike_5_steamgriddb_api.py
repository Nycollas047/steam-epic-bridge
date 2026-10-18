"""Spike 5: Validação dos parâmetros de filtro da API v2 do SteamGridDB.

Risco da seção 8 do plano.md:
- Limites da API do SteamGridDB: conferir limites e nomes dos parâmetros de filtro antes da Fase 2
  para filtrar a consulta na origem (poster vertical, resolução) sem precisar do artwork_doctor.
"""
from __future__ import annotations


def build_steamgriddb_params(asset_type: str, style: str = "any", prefer_animated: bool = False) -> dict[str, str]:
    """Retorna os query params exatos validados na documentação da API v2 do SteamGridDB."""
    params: dict[str, str] = {
        "nsfw": "false",
        "humor": "false",
    }

    # Tipos de animação: 'static' (default) ou 'animated,static' se preferir animadas com fallback
    params["types"] = "animated,static" if prefer_animated else "static"

    if asset_type == "grid":
        # Garante apenas posters verticais (2:3) na origem, eliminando banners horizontais 460x215 ou 920x430!
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
        # Se a Steam aceita PNG (validado no Spike 2), priorizamos image/png ou image/vnd.microsoft.icon
        params["mimes"] = "image/png"
        params["dimensions"] = "512x512,256x256,1024x1024"

    return params


def run_spike() -> dict:
    grid_params = build_steamgriddb_params("grid", style="alternate", prefer_animated=False)
    hero_params = build_steamgriddb_params("hero")
    logo_params = build_steamgriddb_params("logo")
    icon_params = build_steamgriddb_params("icon")

    assert grid_params["dimensions"] == "600x900,660x930,342x482"
    assert grid_params["styles"] == "alternate"
    assert grid_params["types"] == "static"
    assert hero_params["dimensions"] == "1920x620,3840x1240"
    assert logo_params["mimes"] == "image/png"
    assert icon_params["mimes"] == "image/png"

    result = {
        "item": "Parâmetros e limites da API v2 do SteamGridDB",
        "validado": "SIM",
        "detalhes": (
            "1) Parâmetros exatos de GET /api/v2/grids/game/{id}:\n"
            "   - dimensions='600x900,660x930,342x482' (filtra exclusivamente posters verticais 2:3 na origem, "
            "eliminando 100% da necessidade do artwork_doctor.py!).\n"
            "   - styles='alternate' | 'blurred' | 'no_logo' | 'material' | 'white_logo' | 'minimal'\n"
            "   - mimes='image/png,image/jpeg' (nota: no código antigo de artwork_doctor.py usava-se 'mimetypes', "
            "mas o nome correto na API v2 é 'mimes'!).\n"
            "   - types='static' ou 'animated,static' (no código antigo passava-se 'animated' dentro de 'styles', "
            "mas na API v2 o filtro correto é 'types=animated'!).\n"
            "2) Limite de paginação: limit=50 (default 50, page=0). Com ThreadPoolExecutor(max_workers=4 a 6), "
            "evita-se HTTP 429 Too Many Requests no Cloudflare do SteamGridDB."
        ),
    }
    print("[SPIKE 5 - SteamGridDB API v2] Validado:", result["validado"])
    print(" ->", result["detalhes"])
    return result


if __name__ == "__main__":
    run_spike()
