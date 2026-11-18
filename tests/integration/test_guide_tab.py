def test_guide_tab_opens_with_the_documented_sections(stack):
    notebook = stack.window._notebook
    before = len(notebook.tabs())

    stack.window._open_guide_tab()

    assert len(notebook.tabs()) == before + 1
    assert "Guide" in notebook.tab(notebook.tabs()[-1], "text")
    body = stack.window._guide_panel._text.get("1.0", "end")
    assert "Load more" in body
    assert "Diagnostics" in body


def test_opening_the_guide_twice_reuses_the_tab(stack):
    stack.window._open_guide_tab()
    stack.window._open_guide_tab()
    assert len(stack.window._notebook.tabs()) == 3


def test_guide_tab_can_be_closed(stack):
    stack.window._open_guide_tab()
    stack.window._close_guide_tab()
    assert len(stack.window._notebook.tabs()) == 2
    assert stack.window._guide_panel is None


def test_guide_closes_from_its_own_button(stack):
    stack.window._open_guide_tab()
    stack.window._guide_panel._close_btn.invoke()
    assert len(stack.window._notebook.tabs()) == 2
    assert stack.window._guide_panel is None


def test_f1_shortcut_is_bound_to_the_guide(stack):
    # The window may not own the X focus in CI, so assert the binding instead
    # of synthesising a key event that never reaches it.
    assert stack.window._root.bind("<F1>")


def test_view_menu_entry_opens_the_guide(stack):
    menubar = stack.window._menubar
    view_index = next(
        i for i in range(1, menubar.index("end") + 1) if menubar.entrycget(i, "label") == "View"
    )
    view_menu = menubar.nametowidget(menubar.entrycget(view_index, "menu"))
    entry = next(
        i
        for i in range(view_menu.index("end") + 1)
        if view_menu.type(i) == "command" and "User Guide" in str(view_menu.entrycget(i, "label"))
    )
    view_menu.invoke(entry)
    assert stack.window._guide_panel is not None
