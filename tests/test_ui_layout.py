"""Static UI safety checks for Prometheus One.

These tests do not require Flet to be installed. They guard against a Flutter
layout failure caused by Expanded/expand=True being used as a direct child of a
wrapped Row (which is rendered as a Wrap rather than a Flex).
"""
from __future__ import annotations

import ast
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _is_row_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Row"
    )


def _true_keyword(call: ast.Call, name: str) -> bool:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _controls_list(call: ast.Call) -> ast.List | None:
    for kw in call.keywords:
        if kw.arg == "controls" and isinstance(kw.value, ast.List):
            return kw.value
    return None


def _direct_control_expands(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return _true_keyword(node, "expand")


def test_no_expanded_direct_children_in_wrapped_rows() -> None:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    violations: list[int] = []
    for node in ast.walk(tree):
        if not _is_row_call(node) or not _true_keyword(node, "wrap"):
            continue
        controls = _controls_list(node)
        if controls is None:
            continue
        for child in controls.elts:
            if _direct_control_expands(child):
                violations.append(getattr(child, "lineno", getattr(node, "lineno", 0)))
    assert not violations, f"Wrapped Row has direct expand=True child at line(s): {violations}"


def test_logout_is_available_on_desktop_mobile_and_profile() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'secondary_button("Logout", lambda e: logout(), ft.Icons.LOGOUT)' in source
    assert source.count('secondary_button("Logout", lambda e: logout(), ft.Icons.LOGOUT)') >= 2
    assert 'secondary_button("Logout of Prometheus One", lambda e: logout(), ft.Icons.LOGOUT)' in source


if __name__ == "__main__":
    test_no_expanded_direct_children_in_wrapped_rows()
    test_logout_is_available_on_desktop_mobile_and_profile()
    print("PASS — UI layout regression guard and logout entry points are valid.")
