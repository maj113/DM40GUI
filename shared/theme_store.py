from shared.types import ThemePalette


_COLORS_BLOCK = 7 * 10


def deserialize_theme_store_palettes(data: bytes) -> list[ThemePalette]:
    if not data:
        raise ValueError("Theme store is empty")

    raw = data
    body = raw.decode("latin1")
    body_len = len(body)
    offset = 0
    palettes: list[ThemePalette] = []
    append_palette = palettes.append
    colors_block_len = _COLORS_BLOCK
    theme_palette = ThemePalette

    while offset < body_len:

        name_len = raw[offset]
        offset += 1

        if (end := offset + name_len) > body_len:
            raise ValueError("Truncated theme store (name data)")

        name = body[offset:end]
        offset = end

        if (end := offset + colors_block_len) > body_len:
            raise ValueError("Truncated theme store (color data)")

        block = body[offset:end]
        offset = end

        append_palette(theme_palette(
            name,
            block[0:7],
            block[7:14],
            block[14:21],
            block[21:28],
            block[28:35],
            block[35:42],
            block[42:49],
            block[49:56],
            block[56:63],
            block[63:70],
        ))

    return palettes
