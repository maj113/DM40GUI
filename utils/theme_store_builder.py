import argparse
import json
from pathlib import Path

THEME_KEYS = (
    "bg",
    "widget",
    "text",
    "accent",
    "accent_hover",
    "accent_pressed",
    "outline",
    "alt_text",
    "hover",
    "button",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = PROJECT_ROOT / "utils" / "themes.json"
THEME_FIELD_COUNT = 11
COLOR_COUNT = THEME_FIELD_COUNT - 1
COLOR_SIZE = 7
COLORS_BLOCK = COLOR_SIZE * COLOR_COUNT
COLOR_PREFIXES = "#" * COLOR_COUNT


def theme_tuple(entry: dict[str, str]) -> tuple[str, ...]:
    return (entry["name"], *(entry[key] for key in THEME_KEYS))


def serialize_theme_store(themes: list[tuple[str, ...]]) -> bytes:
    if not themes:
        raise ValueError("Theme list cannot be empty")

    chunks: list[bytes] = []
    chunks_extend = chunks.extend
    latin1 = "latin1"
    str_join = "".join

    for theme in themes:
        if len(theme) != THEME_FIELD_COUNT:
            raise ValueError(
                f"Theme must have {THEME_FIELD_COUNT} fields, got {len(theme)}"
            )

        if (name_len := len(name_bytes := theme[0].encode(latin1))) > 0xFF:
            raise ValueError("Theme name too long (max 255 bytes)")

        colors_block = str_join(theme[1:])
        if (
            len(colors_block) != COLORS_BLOCK
            or colors_block[::COLOR_SIZE] != COLOR_PREFIXES
        ):
            raise ValueError(f"Invalid colors for theme: {theme[0]!r}")

        chunks_extend((bytes((name_len,)), name_bytes, colors_block.encode(latin1)))

    return b"".join(chunks)


def main() -> None:
    try:
        from shared.theme_store import deserialize_theme_store_palettes
    except ModuleNotFoundError as exc:
        if __package__ in (None, ""):
            raise SystemExit(
                "Run this script as a module from project root: python -m utils.theme_store_builder"
            ) from exc
        raise

    parser = argparse.ArgumentParser(
        description="Convert theme JSON into a Python bytes literal for embedding."
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON,
        help="Source theme JSON path (default: <project>/utils/themes.json).",
    )
    args = parser.parse_args()

    with args.json.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        raw_themes = payload
    else:
        raw_themes = payload["themes"]

    themes = [theme_tuple(entry) for entry in raw_themes]

    json_size = args.json.stat().st_size
    encoded = serialize_theme_store(themes)
    decoded_themes = deserialize_theme_store_palettes(encoded)

    print(f"_DEFAULT_STORE = {encoded!r}")
    print(f"# {len(decoded_themes)} themes, first={decoded_themes[0].name!r}")
    print(f"# Source: {args.json} ({json_size:,} bytes) -> {len(encoded):,} bytes")


if __name__ == "__main__":
    main()
