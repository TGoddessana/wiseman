def test_package_imports_and_has_version():
    import wiseman_mcp
    assert isinstance(wiseman_mcp.__version__, str)
    assert wiseman_mcp.__version__
