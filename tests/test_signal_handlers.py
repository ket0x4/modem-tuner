"""Static check for GTK signal handlers with the wrong arity.

PyGObject calls a signal handler with every signal argument. A handler passed
straight to ``connect("clicked", self._method)`` therefore needs to accept the
button, or the call fails with a TypeError that GTK only logs — the button
silently does nothing. Guard against that regression without needing a display.
"""

import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


class TestClickHandlers(unittest.TestCase):
    def test_clicked_handlers_accept_the_button(self):
        problems = []
        for path in SRC.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for cls in (node for node in ast.walk(tree)
                        if isinstance(node, ast.ClassDef)):
                methods = {
                    node.name: node for node in cls.body
                    if isinstance(node, ast.FunctionDef)
                }
                for call in ast.walk(cls):
                    if not isinstance(call, ast.Call) or len(call.args) < 2:
                        continue
                    func = call.func
                    if not (isinstance(func, ast.Attribute) and func.attr == "connect"):
                        continue
                    signal = call.args[0]
                    if not (isinstance(signal, ast.Constant)
                            and signal.value == "clicked"):
                        continue
                    handler = call.args[1]
                    if not (isinstance(handler, ast.Attribute)
                            and isinstance(handler.value, ast.Name)
                            and handler.value.id == "self"):
                        continue
                    method = methods.get(handler.attr)
                    if method is None:
                        continue
                    params = len(method.args.args)
                    if params < 2 and method.args.vararg is None:
                        problems.append(
                            f"{path.relative_to(SRC)}:{call.lineno} "
                            f"self.{handler.attr}")
        self.assertEqual(
            problems, [],
            "clicked handlers must accept the button argument (got: "
            + ", ".join(problems) + ")")


if __name__ == "__main__":
    unittest.main()
