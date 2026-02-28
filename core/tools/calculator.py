"""Calculator tool for Synapse Agent."""

import ast
import operator
from .base import BaseTool, ToolResult

# Safe operations for eval
SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


class CalculatorTool(BaseTool):
    """Evaluate mathematical expressions safely."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Evaluate mathematical expressions. Supports +, -, *, /, %, **."

    async def execute(self, params: dict) -> ToolResult:
        expression = params.get("expression", "")
        if not expression:
            return ToolResult(success=False, output="", error="No expression provided")
        try:
            result = self._safe_eval(expression)
            return ToolResult(
                success=True,
                output=f"{expression} = {result}",
                data={"expression": expression, "result": result},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Calculation error: {str(e)}")

    def _safe_eval(self, expression: str):
        """Safely evaluate a mathematical expression using AST."""
        tree = ast.parse(expression, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant: {node.value}")
        elif isinstance(node, ast.BinOp):
            op_func = SAFE_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op_func(self._eval_node(node.left), self._eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_func = SAFE_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op_func(self._eval_node(node.operand))
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")
