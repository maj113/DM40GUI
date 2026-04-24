if '__compiled__' in globals():  # type: ignore[name-defined]
    import shims
    shims.install()

def main() -> None:
    from shared.base_app import App
    App().mainloop()

if __name__ == "__main__":
    main()
