# Shims

This folder contains minimal shim implementations used by the release build.

## Why It Exists

The release build is a one-file Nuitka executable. Some stdlib modules bring in large transitive imports and increase compiled size.

The shipping build installs only the `ctypes` shim.

## Build Flow

Release-path shims use a two-stage flow:

1. Source implementation in `*_shim.py`
2. Compiled bytecode in `*.pyc` when the release build needs that shim

Nuitka embeds those `.pyc` files as frozen bytecode modules.

## Runtime Installation

`main.py` installs shims early:

```py
import shims
shims.install()
```

`shims.install()` injects release-path shim modules into `sys.modules`. It must run before code that imports the corresponding stdlib modules.

## Shimmed Modules

| Shim source | Installed as | Purpose |
|---|---|---|
| `ctypes_shim.py` | `ctypes` | Windows-focused ctypes subset (`WinDLL`, `POINTER`, `wintypes`, etc.) |

Modules not needed by the app are excluded in `build_release.cmd` with `--nofollow-import-to`.

## Limitations

These are intentionally not full stdlib replacements.

- API coverage is partial by design.
- They are safe only for this app and current frozen-build constraints.
- If new code needs missing functionality, either expand the shim deliberately or stop shimming that module.

## Adding or Updating a Shim

1. Add or update `shims/<name>_shim.py` with the smallest required API surface.
2. Add a `py_compile.compile()` step in `build_release.cmd` for `shims/<name>.pyc`.
3. Register it in `shims/__init__.py` via `sys.modules.update(...)`.
4. Ensure the real module remains excluded from freeze inputs via `--nofollow-import-to` when the release build installs the shim.
