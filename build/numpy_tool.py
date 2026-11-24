#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""numpy 计算工具：给 Agent 用，但只允许白名单里的运算。

不使用 eval：把表达式解析成 AST，只放行数字、列表、四则运算、矩阵乘法和
白名单里的 numpy 函数/方法。想扩大能力就往 FUNCS / METHODS 里加。
"""
import ast
import operator

import numpy as np

MAX_SIZE = 200_000          # 结果元素上限，防止把内存打爆

FUNCS = {
    "array": np.array, "asarray": np.asarray,
    "mean": np.mean, "median": np.median, "std": np.std, "var": np.var,
    "sum": np.sum, "prod": np.prod, "min": np.min, "max": np.max,
    "argmin": np.argmin, "argmax": np.argmax, "sort": np.sort,
    "cumsum": np.cumsum, "round": np.round, "abs": np.abs,
    "sqrt": np.sqrt, "exp": np.exp, "log": np.log, "power": np.power,
    "dot": np.dot, "matmul": np.matmul, "transpose": np.transpose,
    "norm": np.linalg.norm, "inv": np.linalg.inv, "det": np.linalg.det,
    "reshape": np.reshape, "linspace": np.linspace, "arange": np.arange,
    "corrcoef": np.corrcoef, "percentile": np.percentile,
}

METHODS = {"mean", "sum", "std", "var", "min", "max", "reshape", "round",
           "argmin", "argmax", "cumsum", "dot", "tolist", "flatten", "ravel"}
ATTRS = {"T", "shape", "size", "ndim"}

OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.MatMult: operator.matmul,
}


class CalcError(ValueError):
    pass


def _check_size(value):
    if isinstance(value, np.ndarray) and value.size > MAX_SIZE:
        raise CalcError(f"结果太大：{value.size} 个元素，上限 {MAX_SIZE}")


def _resolve_func(node):
    # np.mean(...)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "np":
        if node.attr in FUNCS:
            return FUNCS[node.attr]
        raise CalcError(f"不支持的 numpy 函数：np.{node.attr}")
    # 直接 mean(...)
    if isinstance(node, ast.Name) and node.id in FUNCS:
        return FUNCS[node.id]
    # 方法调用：arr.mean(...) / result.reshape(...)
    if isinstance(node, ast.Attribute):
        base = _eval(node.value)
        if node.attr in METHODS:
            return getattr(base, node.attr)
        raise CalcError(f"不支持的方法：.{node.attr}")
    raise CalcError("只支持白名单函数调用")


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, (ast.List, ast.Tuple)):
        return np.array([_eval(e) for e in node.elts])

    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else +v

    if isinstance(node, ast.Attribute):
        base = _eval(node.value)
        if node.attr in ATTRS:
            return getattr(base, node.attr)
        raise CalcError(f"不支持的属性：.{node.attr}")

    if isinstance(node, ast.Subscript):
        base, idx = _eval(node.value), _eval(node.slice)
        return base[idx]

    if isinstance(node, ast.Call):
        func = _resolve_func(node.func)
        args = [_eval(a) for a in node.args]
        kwargs = {kw.arg: _eval(kw.value) for kw in node.keywords}
        if func in (np.arange, np.linspace) and args:
            biggest = max(abs(float(a)) for a in args if isinstance(a, (int, float)))
            if biggest > 1_000_000:
                raise CalcError("arange/linspace 参数太大")
        result = func(*args, **kwargs)
        _check_size(result)
        return result

    raise CalcError(f"不支持的语法：{type(node).__name__}")


def _format(value):
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return "[]"
        return np.array2string(value, precision=4, suppress_small=True, separator=", ")
    if isinstance(value, np.floating):
        return f"{float(value):.6g}"
    if isinstance(value, np.integer):
        return str(int(value))
    if isinstance(value, (list, tuple)):
        return str(value)
    return str(value)


def evaluate(expression: str) -> str:
    """计算表达式并返回文本结果；出错抛 CalcError。"""
    if len(expression) > 2000:
        raise CalcError("表达式太长")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise CalcError(f"语法错误：{e.msg}")
    return _format(_eval(tree.body))
