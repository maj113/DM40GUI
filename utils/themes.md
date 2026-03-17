# Themes

This file explains how themes are defined and loaded.

## Runtime Model

`GUI/theme_manager.py` is the runtime source of truth.

- Theme bytes are embedded in `_DEFAULT_STORE`.
- `ThemeManager` loads palettes with `deserialize_theme_store_palettes(_DEFAULT_STORE)`.
- Active theme selection is index-based.

Theme persistence uses the Windows registry:

- Key: `HKEY_CURRENT_USER\Software\DM40`
- Value: `active_theme` (`REG_DWORD`)

Only the selected index is persisted. Theme definitions are static until `_DEFAULT_STORE` is regenerated.

## Theme Schema

Themes map to `ThemePalette` in `dm40/types.py` and must provide exactly 14 fields in this order:

1. `name`
2. `bg`
3. `panel`
4. `widget`
5. `text`
6. `muted`
7. `accent`
8. `accent_hover`
9. `accent_pressed`
10. `outline`
11. `alt_text`
12. `hover`
13. `button`
14. `button_pressed`

All color values must use `#RRGGBB` format.

## Embedded Store Format

`dm40/theme_store.py` encodes themes as back-to-back records with no global header.

Per theme record:

- 1 byte: name length
- N bytes: name (`latin1`)
- 91 bytes: color payload (`13 * 7`)

Validation in `serialize_theme_store` enforces:

- at least one theme
- exactly 14 fields per theme
- name length <= 255 bytes
- color payload length of 91
- each color starts with `#`

## Updating Themes

1. Edit `utils/themes.json`.
2. Run from repo root:

  ```powershell
  python -m utils.theme_store_builder --json utils/themes.json
  ```

3. Copy the generated `_DEFAULT_STORE = b'...'` value.
4. Replace `_DEFAULT_STORE` in `GUI/theme_manager.py`.
5. Run the app and verify:
  theme browser preview/apply, startup theme restore, and registry persistence.
