if '__compiled__' in globals(): # type: ignore[name-defined]
    import shims
    shims.install()

def main() -> None:
    from dm40.app import DM40App

    app = DM40App()
    app.mainloop()

if __name__ == "__main__":
    main()
