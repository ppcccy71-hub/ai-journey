#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单元测试：证明代码层能挡住越界路径（不依赖模型）。"""
import unittest

import step13_agent as agent


class TestSafePath(unittest.TestCase):
    def test_traversal_blocked(self):
        with self.assertRaises(ValueError):
            agent.safe_path("../hack.txt")

    def test_nested_traversal_blocked(self):
        with self.assertRaises(ValueError):
            agent.safe_path("sub/../../hack.txt")

    def test_absolute_path_blocked(self):
        with self.assertRaises(ValueError):
            agent.safe_path("C:/Windows/system.ini")

    def test_normal_name_ok(self):
        p = agent.safe_path("report.md")
        self.assertEqual(p.name, "report.md")


if __name__ == "__main__":
    unittest.main()