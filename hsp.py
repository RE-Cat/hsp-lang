#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPS 解释器 v0.3.0

作者: RE-Cat
GitHub: https://github.com/RE-Cat/HSP-Hermesian-probability-
"""

import re
import random
import cmd
import sys
import argparse
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Pool:
    name: str
    total_prob: float
    items: List[str]


@dataclass
class Function:
    name: str
    params: List[str]
    body: List[str]


class HPSInterpreter:
    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.pools: Dict[str, Pool] = {}
        self.currency: Dict[str, float] = {}
        self.inventory: List[str] = []
        self.pity_counter: int = 0
        self.total_spent: float = 0
        self.functions: Dict[str, Function] = {}
        self.output_lines: List[str] = []
        self.in_function = False
        self.current_function_lines: List[str] = []
        self.current_function_name: str = ""
        self.current_function_params: List[str] = []

    def reset(self):
        self.__init__()

    def execute(self, line: str, show_prompt: bool = False) -> List[str]:
        self.output_lines = []
        line = line.strip()
        if not line:
            return []

        if show_prompt and not self.in_function:
            print(f"hps> {line}")

        try:
            self._execute_line(line)
        except Exception as e:
            self.output_lines.append(f"[!] {str(e)}")

        return self.output_lines

    def run_script(self, code: str, verbose: bool = True) -> None:
        lines = code.strip().split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # 处理函数定义（多行）
            if line.startswith('¢.') and not self.in_function:
                # 收集函数体
                self._start_function_def(line)
                i += 1
                while i < len(lines):
                    func_line = lines[i].strip()
                    if func_line == '¢.End':
                        self._end_function_def()
                        break
                    self.current_function_lines.append(func_line)
                    i += 1
                i += 1
                continue

            outputs = self.execute(line, show_prompt=False)
            if verbose:
                for out in outputs:
                    print(out)
            i += 1

    def _start_function_def(self, line: str):
        """开始函数定义"""
        match = re.match(r'¢\.(\w+)\(([^)]*)\)', line)
        if not match:
            raise ValueError("函数定义: ¢.函数名(参数)")

        self.current_function_name = match.group(1)
        params_str = match.group(2).strip()
        self.current_function_params = [p.strip() for p in params_str.split(',')] if params_str else []
        self.current_function_lines = []
        self.in_function = True

    def _end_function_def(self):
        """结束函数定义"""
        func = Function(
            self.current_function_name,
            self.current_function_params,
            self.current_function_lines
        )
        self.functions[self.current_function_name] = func
        self.output_lines.append(f"[函] ¢.{self.current_function_name} 定义完成")
        self.in_function = False
        self.current_function_name = ""
        self.current_function_params = []
        self.current_function_lines = []

    def _execute_line(self, line: str):
        # 如果在函数定义中，只收集不执行
        if self.in_function and not line.startswith('¢.'):
            self.current_function_lines.append(line)
            return

        # 输出
        if line.startswith('¢,'):
            self._handle_output(line)
            return

        # 注释
        if line.startswith('¢') and not line.startswith('¢.'):
            comment = line[1:].strip()
            if comment:
                self.output_lines.append(f"[注] {comment}")
            return

        # 函数定义开始
        if line.startswith('¢.') and '¢.End' not in line:
            # 单行函数或开始多行函数
            if line.endswith(')'):
                self._start_function_def(line)
            return

        # 函数定义结束
        if line == '¢.End':
            self._end_function_def()
            return

        # 函数调用
        if re.match(r'^(?!¢\.)\w+\([^)]*\)$', line) and '(' in line:
            self._call_function(line)
            return

        # return 语句
        if line.startswith('return'):
            self._handle_return(line)
            return

        # 池子定义
        if line.startswith('('):
            self._define_pool(line)
            return

        # 变量赋值
        if line.startswith('#') and '=' in line and not line.startswith('#¢'):
            self._assign_variable(line)
            return

        # 目标抽卡
        if line.startswith('<'):
            self._execute_target(line)
            return

        # 数学运算
        if line.startswith('&A('):
            self._handle_math(line)
            return


        # 条件
        if line.startswith('?'):
            self._handle_condition(line)
            return

        # 特殊命令
        if line == '/state':
            self.output_lines.append(self.get_state())
            return
        if line == '/reset':
            self.reset()
            self.output_lines.append("[✓] 已重置")
            return

        if line in ['exit', 'quit']:
            self.output_lines.append("[bye]")
            return

        self.output_lines.append(f"[?] 未知: {line[:40]}")

    def _define_pool(self, line: str):
        prob_match = re.search(r'\(([\d.]+)/', line)
        if not prob_match:
            raise ValueError("池子: (0.6/:$雷电)#UP")

        total_prob = float(prob_match.group(1)) / 100
        items = re.findall(r'\$(\w+)', line)

        if not items:
            raise ValueError("池子需要物品")

        name_match = re.search(r'#(\w+)', line)
        if not name_match:
            raise ValueError("池子需要命名")

        pool_name = name_match.group(1)
        self.pools[pool_name] = Pool(pool_name, total_prob, items)

        items_str = ','.join(f'${i}' for i in items)
        self.output_lines.append(f"[池] #{pool_name} | {total_prob*100}% | {items_str}")

    def _assign_variable(self, line: str):
        match = re.match(r'#(\w+)\s*=\s*(.+)', line)
        if not match:
            raise ValueError("赋值: #变量 = 值")

        name, value_str = match.groups()
        value_str = value_str.strip()

        if value_str.startswith('¥'):
            self.currency[name] = float(value_str[1:])
        elif value_str.endswith('/'):
            prob_match = re.search(r'([\d.]+)/', value_str)
            if prob_match:
                self.variables[name] = float(prob_match.group(1)) / 100
        else:
            try:
                self.variables[name] = float(value_str)
            except:
                self.variables[name] = value_str

        self.output_lines.append(f"[变] #{name} = {value_str}")

    def _execute_target(self, line: str):
        item_match = re.search(r'\$(\w+)', line)
        if not item_match:
            raise ValueError("目标: <$雷电,#UP,*90>")
        target_item = item_match.group(1)

        pool_match = re.search(r'#(\w+)', line)
        if not pool_match or pool_match.group(1) not in self.pools:
            raise ValueError(f"池子未定义")
        pool_name = pool_match.group(1)
        pool = self.pools[pool_name]

        times_match = re.search(r'×:(\d+)', line)
        draw_times = int(times_match.group(1)) if times_match else 1

        pity_match = re.search(r'\*(\d+)', line)
        max_pity = int(pity_match.group(1)) if pity_match else 90

        self.output_lines.append(f"[抽] ${target_item} | #{pool_name} | {draw_times}连 | 保底{max_pity}")

        for draw in range(1, max_pity + 1):
            self.pity_counter += 1
            current_prob = pool.total_prob

            if self.pity_counter > 70:
                current_prob = min(1.0, current_prob + (self.pity_counter - 70) * 0.02)

            if random.random() < current_prob:
                drawn = random.choice(pool.items)
                self.inventory.append(drawn)

                if draw <= 3 or drawn == target_item or draw >= max_pity - 2:
                    pity_tag = f"[{self.pity_counter}]" if self.pity_counter > 70 else ""
                    self.output_lines.append(f"     第{draw}抽: ${drawn} {pity_tag}")

                if drawn == target_item:
                    cost = draw * 160
                    self.total_spent += cost
                    self.output_lines.append(f"[✓] 出货! ${target_item} | {draw}抽 ¥{cost}")
                    self.pity_counter = 0
                    return
                break
        else:
            self.inventory.append(target_item)
            cost = max_pity * 160
            self.total_spent += cost
            self.output_lines.append(f"[!] 保底 | ${target_item} | {max_pity}抽 ¥{cost}")
            self.pity_counter = 0

    def _handle_output(self, line: str):
        content = line[2:]

        def replace_var(match):
            var_name = match.group(1)
            if var_name in self.variables:
                val = self.variables[var_name]
                if isinstance(val, float) and val < 1:
                    return f"{val*100}%"
                return str(val)
            elif var_name in self.currency:
                return f"¥{self.currency[var_name]}"
            return f"[未定义:#{var_name}]"

        content = re.sub(r'#(\w+)', replace_var, content)
        content = content.replace('{inventory}', str(self.inventory))
        content = content.replace('{total_spent}', f'¥{self.total_spent}')
        content = content.replace('{pity}', str(self.pity_counter))

        self.output_lines.append(f"[出] {content}")

    def _handle_math(self, line: str):
        match = re.search(r'&A\((.+)\)', line)
        if match:
            expr = match.group(1)
            for var, val in self.variables.items():
                expr = expr.replace(f'#{var}', str(val))
            for var, val in self.currency.items():
                expr = expr.replace(f'#{var}', str(val))

            expr = expr.replace('×', '*').replace('÷', '/')

            try:
                result = eval(expr, {"__builtins__": {}}, {})
                self.output_lines.append(f"[算] {match.group(1)} = {result:.2f}")
            except:
                self.output_lines.append(f"[算] 错误: {expr}")


    def _call_function(self, line: str):
        """调用函数"""
        match = re.match(r'(\w+)\(([^)]*)\)', line)
        if not match:
            return

        func_name = match.group(1)
        args_str = match.group(2).strip()
        args = [a.strip() for a in args_str.split(',')] if args_str else []

        if func_name not in self.functions:
            self.output_lines.append(f"[!] 函数未定义: {func_name}")
            return

        func = self.functions[func_name]
        self.output_lines.append(f"[调] ¢.{func_name}({args_str})")

        # 执行函数体
        for body_line in func.body:
            body_line = body_line.strip()
            if not body_line:
                continue

            # 替换参数
            for i, param in enumerate(func.params):
                if i < len(args):
                    body_line = body_line.replace(f'#{param}', args[i])

            # 执行
            outputs = self.execute(body_line, show_prompt=False)
            for out in outputs:
                if not out.startswith('[函]'):
                    self.output_lines.append(f"  {out}")

    def _handle_return(self, line: str):
        """处理 return"""
        match = re.match(r'return\s*(.+)', line)
        if match:
            value = match.group(1).strip()
            self.output_lines.append(f"[返] {value}")

    def get_state(self) -> str:
        lines = ["─" * 40]
        lines.append("📊 状态")
        if self.pools:
            lines.append(f"  池: {list(self.pools.keys())}")
        if self.functions:
            lines.append(f"  函: {list(self.functions.keys())}")
        if self.variables:
            vars_display = {}
            for k, v in self.variables.items():
                if isinstance(v, float) and v < 1:
                    vars_display[k] = f"{v*100}%"
                else:
                    vars_display[k] = v
            lines.append(f"  变: {vars_display}")
        if self.currency:
            lines.append(f"  钱: {self.currency}")
        lines.append(f"  库: {self.inventory}")
        lines.append(f"  保: {self.pity_counter} | 花: ¥{self.total_spent}")
        lines.append("─" * 40)
        return "\n".join(lines)


class HPSREPL(cmd.Cmd):
    intro = """
╔══════════════════════════════════════╗
║     HPS 交互模式 v0.3.0              ║
║                                       ║
╚══════════════════════════════════════╝
"""
    prompt = 'hps> '

    def __init__(self):
        super().__init__()
        self.interpreter = HPSInterpreter()

    def default(self, line: str):
        if line.strip() in ['exit', 'quit']:
            print("再见!")
            return True

        outputs = self.interpreter.execute(line, show_prompt=True)
        for out in outputs:
            print(out)

    def do_state(self, arg):
        print(self.interpreter.get_state())

    def do_reset(self, arg):
        self.interpreter.reset()
        print("[✓] 已重置")

    def do_run(self, filepath: str):
        if not filepath.strip():
            print("[!] 用法: /run 文件.hps")
            return
        try:
            with open(filepath.strip(), 'r', encoding='utf-8') as f:
                code = f.read()
            print(f"\n[运行] {filepath}")
            print("=" * 40)
            self.interpreter.run_script(code, verbose=True)
            print("=" * 40)
            print("[✓] 完成\n")
        except FileNotFoundError:
            print(f"[!] 找不到: {filepath}")

    def do_help(self, arg):
        print("""
📘 HPS v0.3.0 语法:
═══════════════════════
基础:
  ¢ 注释              注释
  ¢,内容              输出
  (0.6/:$雷电)#UP     定义池子
  #预算 = ¥64800      变量赋值
  <$雷电,#UP,*90>     抽卡
  &A(1 ÷ 0.006)       数学计算

函数:
  ¢.函数名(参数)      定义函数
    ...               函数体
  ¢.End               结束定义
  函数名(参数)        调用函数

命令:
  /state  查看状态
  /reset  重置
  exit    退出
""")

    def do_exit(self, arg):
        print("再见!")
        return True

    def emptyline(self):
        pass


def main():
    parser = argparse.ArgumentParser(description='HPS 解释器 v0.3.0')
    parser.add_argument('file', nargs='?', help='HPS 脚本')
    parser.add_argument('-i', '--interactive', action='store_true')
    args = parser.parse_args()

    if args.file:
        interp = HPSInterpreter()
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                code = f.read()
            print(f"[HPS] 运行: {args.file}\n")
            interp.run_script(code, verbose=True)
            if args.interactive:
                print()
                repl = HPSREPL()
                repl.interpreter = interp
                repl.cmdloop()
        except Exception as e:
            print(f"[!] 错误: {e}")
            sys.exit(1)
    else:
        repl = HPSREPL()
        repl.cmdloop()


if __name__ == "__main__":
    main()
