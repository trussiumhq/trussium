from trussium import __main__


def test_main_module_exists() -> None:
    assert callable(__main__.main)
