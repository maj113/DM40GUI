if '__compiled__' in globals(): # type: ignore[name-defined]
    import shims
    shims.install()

def main() -> None:
    import tkinter as tk
    from GUI.widgets.helpers import ensure_dpi_awareness
    from GUI.launcher import LauncherWindow

    root = tk.Tk()
    root.withdraw()
    ensure_dpi_awareness()

    _app_window = None

    def on_connect(device, device_type) -> None:
        nonlocal _app_window
        launcher.withdraw()

        if device_type == "EL15":
            from el15.app import EL15App
            app = EL15App(root)
        elif device_type == "DM40":
            from dm40.app import DM40App
            app = DM40App(root)
        else:
            from GUI.themed_messagebox import show_error
            launcher.deiconify()
            show_error(launcher, "Unsupported Device",
                       f"'{device.name}' is not a recognised DM40 or EL15 device.",
                       theme=(launcher.ui.theme.bg, launcher.ui.theme.outline))
            return
        _app_window = app

        def on_app_close():
            app.disconnect()
            app.destroy()
            launcher.deiconify()

        app.protocol("WM_DELETE_WINDOW", on_app_close)

        # Pre-select the device and immediately connect
        app._devices = [device]
        app._device_index_by_address[device.address] = 0
        name = device.name or "Unknown"
        app._device_listbox.insert(tk.END, f"{name} ({device.address})")
        app._device_listbox.selection_set(0)
        app.connect()

    launcher = LauncherWindow(root, on_connect=on_connect)
    root.mainloop()

if __name__ == "__main__":
    main()
