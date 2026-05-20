import sys
import re
import os
import math


# ─────────────────────────────────────────────
#  TOKEN
# ─────────────────────────────────────────────

class Token:
    def __init__(self, type: str, value):
        self.type  = type
        self.value = value


# ─────────────────────────────────────────────
#  PRE-PROCESSOR
# ─────────────────────────────────────────────

class PrePro:
    def filter(code: str) -> str:
        # Remove line comments (--)
        lines = code.split("\n")
        result = []
        for line in lines:
            idx = line.find("--")
            if idx >= 0:
                line = line[:idx]
            result.append(line)
        code = "\n".join(result)

        # Replace const declarations
        const_pattern = re.compile(r'^\s*const\s+([A-Za-z][A-Za-z0-9_]*)\s+(\d+)\s*$', re.MULTILINE)
        const_map = {}
        for m in const_pattern.finditer(code):
            const_map[m.group(1)] = m.group(2)
        code = const_pattern.sub('', code)
        for name, val in const_map.items():
            code = re.sub(r'\b' + name + r'\b', val, code)
        return code


# ─────────────────────────────────────────────
#  VARIABLE
# ─────────────────────────────────────────────

class Variable:
    def __init__(self, vartype: str, value=None, shift: int = 0,
                 is_func: bool = False, immut: bool = False, is_param: bool = False):
        self.vartype   = vartype   # "number", "float", "string", "boolean"
        self.value     = value
        self.shift     = shift
        self.is_func   = is_func
        self.immut     = immut
        self.is_param  = is_param

    @staticmethod
    def make_number(v: int):
        return Variable("number", v)

    @staticmethod
    def make_float(f: float):
        return Variable("float", f)

    @staticmethod
    def make_string(s: str):
        return Variable("string", s)

    @staticmethod
    def make_bool(b):
        return Variable("boolean", 1 if b else 0)

    @staticmethod
    def default_for(vartype: str):
        if vartype == "string":   return Variable.make_string("")
        if vartype == "boolean":  return Variable.make_bool(0)
        if vartype == "float":    return Variable.make_float(0.0)
        return Variable.make_number(0)

    def truthy(self) -> bool:
        if self.vartype == "string":  return self.value != ""
        if self.vartype == "float":   return self.value != 0.0
        return self.value != 0

    def to_float(self) -> float:
        if self.vartype == "float": return self.value
        return float(self.value)

    def is_numeric(self) -> bool:
        return self.vartype in ("number", "float")

    def to_str(self) -> str:
        if self.vartype == "string":  return self.value
        if self.vartype == "boolean": return "true" if self.value else "false"
        if self.vartype == "float":
            # remove trailing zeros like Go's %f -1
            s = f"{self.value}"
            return s
        return str(self.value)


# ─────────────────────────────────────────────
#  SYMBOL TABLE
# ─────────────────────────────────────────────

class SymbolTable:
    def __init__(self, parent=None):
        self.table  = {}
        self.offset = 0
        self.parent = parent
        self.inside_function = False

    def is_inside_function(self) -> bool:
        if self.inside_function: return True
        if self.parent:          return self.parent.is_inside_function()
        return False

    def create_variable(self, name: str, vartype: str, is_func: bool = False):
        if name in self.table:
            raise Exception(f"[Semantic] Variable '{name}' already declared")
        self.offset += 4
        v = Variable.default_for(vartype)
        v.shift   = self.offset
        v.is_func = is_func
        self.table[name] = v

    def get_value(self, name: str) -> Variable:
        if name in self.table:
            return self.table[name]
        if self.parent:
            return self.parent.get_value(name)
        raise Exception(f"[Semantic] Undefined variable: {name}")

    def set_value(self, name: str, val: Variable):
        if name in self.table:
            existing = self.table[name]
            if existing.immut:
                raise Exception(f"[Semantic] Cannot change the value of {name}")
            # Functions are stored with vartype="function"; skip the type check for them
            if not existing.is_func and existing.vartype != val.vartype:
                raise Exception(
                    f"[Semantic] Type mismatch: cannot assign {val.vartype} "
                    f"to {existing.vartype} variable '{name}'"
                )
            new_var = Variable(val.vartype if existing.is_func else existing.vartype,
                               val.value, existing.shift,
                               existing.is_func, False, existing.is_param)
            self.table[name] = new_var
            return
        if self.parent:
            self.parent.set_value(name, val)
            return
        # root scope: auto-declare
        self.table[name] = val

    def set_immut(self, name: str, val: Variable):
        v = Variable(val.vartype, val.value, val.shift, val.is_func, True, val.is_param)
        self.table[name] = v

    def is_declared(self, name: str) -> bool:
        if name in self.table: return True
        if self.parent:        return self.parent.is_declared(name)
        return False


# ─────────────────────────────────────────────
#  CODE GENERATION
# ─────────────────────────────────────────────

class Code:
    main_instructions = []
    func_instructions = []
    current           = None   # points to main_instructions or func_instructions

    @classmethod
    def reset(cls):
        cls.main_instructions = []
        cls.func_instructions = []
        cls.current = cls.main_instructions

    @classmethod
    def append(cls, line: str):
        cls.current.append(line)

    @classmethod
    def dump(cls, filename: str):
        with open(filename, 'w') as f:
            f.write('section .data\n')
            f.write('  format_out: db "%d", 10, 0\n')
            f.write('  format_in: db "%d", 0\n')
            f.write('  scan_int: dd 0\n\n')
            f.write('section .text\n')
            f.write('  extern printf\n')
            f.write('  extern scanf\n')
            f.write('  global _start\n\n')
            f.write('_start:\n')
            f.write('  push ebp\n')
            f.write('  mov ebp, esp\n\n')
            for line in cls.main_instructions:
                f.write(line + '\n')
            f.write('\n  mov esp, ebp\n')
            f.write('  pop ebp\n')
            f.write('  mov eax, 1\n')
            f.write('  xor ebx, ebx\n')
            f.write('  int 0x80\n')
            if cls.func_instructions:
                f.write('\n')
                for line in cls.func_instructions:
                    f.write(line + '\n')


Code.reset()


# ─────────────────────────────────────────────
#  LEXER
# ─────────────────────────────────────────────

class Lexer:
    RESERVED = {
        "print":    "PRINT",
        "imut":     "IMUT",
        "and":      "AND",
        "or":       "OR",
        "not":      "NOT",
        "if":       "IF",
        "while":    "WHILE",
        "else":     "ELSE",
        "read":     "READ",
        "then":     "THEN",
        "do":       "DO",
        "end":      "KW_END",
        "for":      "FOR",
        "repeat":   "REPEAT",
        "until":    "UNTIL",
        "local":    "VAR",
        "true":     "BOOL",
        "false":    "BOOL",
        "number":   "TYPE",
        "string":   "TYPE",
        "boolean":  "TYPE",
        "float":    "TYPE",
        "function": "FUNCTION",
        "return":   "RETURN",
    }

    def __init__(self, source: str):
        self.source   = source
        self.position = 0
        self.next     = None
        self.select_next()

    def save(self):
        return (self.position, self.next)

    def restore(self, state):
        self.position, self.next = state

    def select_next(self):
        src = self.source
        pos = self.position

        # skip whitespace (not newline)
        while pos < len(src) and src[pos] in (' ', '\t', '\r'):
            pos += 1

        if pos >= len(src):
            self.position = pos
            self.next = Token("EOF", "")
            return

        ch = src[pos]

        # newline
        if ch == '\n':
            self.next = Token("END", "\n")
            self.position = pos + 1
            return

        # float or int
        if ch.isdigit():
            start = pos
            while pos < len(src) and src[pos].isdigit():
                pos += 1
            # float: digit '.' digit — but not '..' concat
            if (pos < len(src) and src[pos] == '.'
                    and not (pos + 1 < len(src) and src[pos + 1] == '.')):
                pos += 1  # consume '.'
                while pos < len(src) and src[pos].isdigit():
                    pos += 1
                self.next = Token("FLOAT_LIT", src[start:pos])
            else:
                self.next = Token("INT", int(src[start:pos]))
            self.position = pos
            return

        # identifier / keyword
        if ch.isalpha() or ch == '_':
            start = pos
            while pos < len(src) and (src[pos].isalnum() or src[pos] == '_'):
                pos += 1
            word = src[start:pos]
            tt = Lexer.RESERVED.get(word, "IDEN")
            self.next = Token(tt, word)
            self.position = pos
            return

        # string literal
        if ch == '"':
            pos += 1
            start = pos
            while pos < len(src) and src[pos] != '"':
                pos += 1
            if pos >= len(src):
                raise Exception("[Lexer] Unterminated string literal")
            s = src[start:pos]
            pos += 1  # consume closing "
            self.next = Token("STR", s)
            self.position = pos
            return

        # two-char or one-char symbols
        if ch == '=' and pos + 1 < len(src) and src[pos + 1] == '=':
            self.next = Token("EQ", "==")
            self.position = pos + 2
        elif ch == '*' and pos + 1 < len(src) and src[pos + 1] == '*':
            self.next = Token("POW", "**")
            self.position = pos + 2
        elif ch == '.' and pos + 1 < len(src) and src[pos + 1] == '.':
            self.next = Token("CONCAT", "..")
            self.position = pos + 2
        elif ch == '|' and pos + 1 < len(src) and src[pos + 1] == '|':
            self.next = Token("OR", "||")
            self.position = pos + 2
        elif ch == '&' and pos + 1 < len(src) and src[pos + 1] == '&':
            self.next = Token("AND", "&&")
            self.position = pos + 2
        elif ch == '=':
            self.next = Token("ASSIGN", "=")
            self.position = pos + 1
        elif ch == '+':
            self.next = Token("PLUS", "+")
            self.position = pos + 1
        elif ch == '-':
            self.next = Token("MINUS", "-")
            self.position = pos + 1
        elif ch == '*':
            self.next = Token("MULT", "*")
            self.position = pos + 1
        elif ch == '/':
            self.next = Token("DIV", "/")
            self.position = pos + 1
        elif ch == '(':
            self.next = Token("OPEN_PAR", "(")
            self.position = pos + 1
        elif ch == ')':
            self.next = Token("CLOSE_PAR", ")")
            self.position = pos + 1
        elif ch == '>':
            self.next = Token("GT", ">")
            self.position = pos + 1
        elif ch == '<':
            self.next = Token("LT", "<")
            self.position = pos + 1
        elif ch == ',':
            self.next = Token("COMMA", ",")
            self.position = pos + 1
        elif ch == '.':
            raise Exception(f"[Lexer] Invalid Symbol {ch}")
        else:
            raise Exception(f"[Lexer] Invalid Symbol {ch}")


# ─────────────────────────────────────────────
#  AST NODES
# ─────────────────────────────────────────────

_node_id_counter = 0

def new_node_id():
    global _node_id_counter
    _node_id_counter += 1
    return _node_id_counter


class Node:
    def __init__(self, value, children=None):
        self.value    = value
        self.children = children or []
        self.uid      = new_node_id()

    def evaluate(self, st: SymbolTable) -> Variable:
        raise NotImplementedError

    def generate(self, st: SymbolTable):
        raise NotImplementedError


# ── Literals ──────────────────────────────────

class IntVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable.make_number(self.value)

    def generate(self, st):
        Code.append(f"  mov eax, {self.value}")


class FloatVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable.make_float(self.value)

    def generate(self, st):
        raise NotImplementedError("[CodeGen] float not supported in assembly generation")


class BoolVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)  # value: True/False or 1/0

    def evaluate(self, st):
        return Variable.make_bool(self.value)

    def generate(self, st):
        Code.append(f"  mov eax, {1 if self.value else 0}")


class StringVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable.make_string(self.value)

    def generate(self, st):
        raise NotImplementedError("[CodeGen] string not supported in assembly generation")


# ── Identifier ────────────────────────────────

class Identifier(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return st.get_value(self.value)

    def generate(self, st):
        v = st.get_value(self.value)
        if v.is_param:
            Code.append(f"  mov eax, [ebp+{v.shift}]")
        else:
            Code.append(f"  mov eax, [ebp-{v.shift}]")


# ── Cast ──────────────────────────────────────

class CastNode(Node):
    """(TYPE) expr"""
    def __init__(self, value, children):
        super().__init__(value, children)  # value = target type string

    def evaluate(self, st):
        val = self.children[0].evaluate(st)
        t   = self.value
        if t == "number":
            if val.vartype == "number":  return Variable.make_number(val.value)
            if val.vartype == "float":   return Variable.make_number(round(val.value))
            if val.vartype == "boolean": return Variable.make_number(val.value)
            if val.vartype == "string":
                try: return Variable.make_number(int(val.value))
                except: raise Exception(f"[Semantic] Cannot cast string '{val.value}' to number")
        if t == "float":
            if val.vartype == "float":   return Variable.make_float(val.value)
            if val.vartype == "number":  return Variable.make_float(float(val.value))
            if val.vartype == "boolean": return Variable.make_float(float(val.value))
            if val.vartype == "string":
                try: return Variable.make_float(float(val.value))
                except: raise Exception(f"[Semantic] Cannot cast string '{val.value}' to float")
        if t == "string":  return Variable.make_string(val.to_str())
        if t == "boolean": return Variable.make_bool(val.truthy())
        raise Exception(f"[Semantic] Unknown cast target type: {t}")

    def generate(self, st):
        raise NotImplementedError("[CodeGen] cast not supported in assembly generation")


# ── Operators ─────────────────────────────────

class UnOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        val = self.children[0].evaluate(st)
        if self.value == "+":
            if not val.is_numeric(): raise Exception("[Semantic] Unary '+' requires number or float")
            return Variable(val.vartype, val.value)
        if self.value == "-":
            if not val.is_numeric(): raise Exception("[Semantic] Unary '-' requires number or float")
            return Variable(val.vartype, -val.value)
        if self.value == "not":
            if val.vartype != "boolean": raise Exception("[Semantic] 'not' requires a boolean operand")
            return Variable.make_bool(not val.value)
        raise Exception(f"[Semantic] Unknown unary operator: {self.value}")

    def generate(self, st):
        self.children[0].generate(st)
        if self.value == "-":   Code.append("  neg eax")
        elif self.value == "not": Code.append("  xor eax, 1")


class BinOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def _numeric_result(self, l, r, i_result, f_result):
        if l.vartype == "float" or r.vartype == "float":
            return Variable.make_float(f_result)
        return Variable.make_number(i_result)

    def evaluate(self, st):
        left  = self.children[0].evaluate(st)
        right = self.children[1].evaluate(st)
        op    = self.value

        if op == "+":
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '+' requires number or float operands")
            return self._numeric_result(left, right,
                left.value + right.value, left.to_float() + right.to_float())
        if op == "-":
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '-' requires number or float operands")
            return self._numeric_result(left, right,
                left.value - right.value, left.to_float() - right.to_float())
        if op == "*":
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '*' requires number or float operands")
            return self._numeric_result(left, right,
                left.value * right.value, left.to_float() * right.to_float())
        if op == "/":
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '/' requires number or float operands")
            if left.vartype == "float" or right.vartype == "float":
                if right.to_float() == 0: raise Exception("[Semantic] Division by zero")
                return Variable.make_float(left.to_float() / right.to_float())
            if right.value == 0: raise Exception("[Semantic] Division by zero")
            return Variable.make_number(left.value // right.value)
        if op == "**":
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '**' requires number or float operands")
            if left.vartype == "float" or right.vartype == "float":
                return Variable.make_float(left.to_float() ** right.to_float())
            result = 1
            for _ in range(right.value): result *= left.value
            return Variable.make_number(result)
        if op == "..":
            return Variable.make_string(left.to_str() + right.to_str())
        if op == "==":
            if left.is_numeric() and right.is_numeric():
                return Variable.make_bool(left.to_float() == right.to_float())
            if left.vartype != right.vartype:
                raise Exception(f"[Semantic] Type mismatch in '==': {left.vartype} vs {right.vartype}")
            if left.vartype == "string": return Variable.make_bool(left.value == right.value)
            return Variable.make_bool(left.value == right.value)
        if op == ">":
            if left.vartype == "string" and right.vartype == "string":
                return Variable.make_bool(left.value > right.value)
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '>' requires number or float operands")
            return Variable.make_bool(left.to_float() > right.to_float())
        if op == "<":
            if left.vartype == "string" and right.vartype == "string":
                return Variable.make_bool(left.value < right.value)
            if not left.is_numeric() or not right.is_numeric():
                raise Exception("[Semantic] Operator '<' requires number or float operands")
            return Variable.make_bool(left.to_float() < right.to_float())
        if op == "and":
            if left.vartype != "boolean" or right.vartype != "boolean":
                raise Exception("[Semantic] 'and' requires boolean operands")
            return Variable.make_bool(left.value and right.value)
        if op == "or":
            if left.vartype != "boolean" or right.vartype != "boolean":
                raise Exception("[Semantic] 'or' requires boolean operands")
            return Variable.make_bool(left.value or right.value)
        raise Exception(f"[Semantic] Unknown binary operator: {op}")

    def generate(self, st):
        op = self.value
        self.children[1].generate(st)   # right → EAX
        Code.append("  push eax")
        self.children[0].generate(st)   # left → EAX
        Code.append("  pop ecx")        # ECX = right
        if op == "+":   Code.append("  add eax, ecx")
        elif op == "-": Code.append("  sub eax, ecx")
        elif op == "*": Code.append("  imul ecx")
        elif op == "/":
            Code.append("  cdq")
            Code.append("  idiv ecx")
        elif op == "==":
            Code.append("  cmp eax, ecx")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmove eax, ecx")
        elif op == ">":
            Code.append("  cmp eax, ecx")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmovg eax, ecx")
        elif op == "<":
            Code.append("  cmp eax, ecx")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmovl eax, ecx")
        elif op == "and": Code.append("  and eax, ecx")
        elif op == "or":  Code.append("  or eax, ecx")
        else: raise NotImplementedError(f"[CodeGen] operator '{op}' not supported in assembly")


# ── Declarations & Assignment ─────────────────

class VarDec(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        name = self.children[0].value
        st.create_variable(name, self.value, is_func=False)
        if len(self.children) > 1:
            val = self.children[1].evaluate(st)
            st.set_value(name, val)

    def generate(self, st):
        name = self.children[0].value
        st.create_variable(name, self.value, is_func=False)
        v = st.table[name]
        Code.append(f"  sub esp, 4 ; var {name} [EBP-{v.shift}]")
        if len(self.children) > 1:
            self.children[1].generate(st)
            Code.append(f"  mov [ebp-{v.shift}], eax")


class ImutAssignment(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        name = self.children[0].value
        val  = self.children[1].evaluate(st)
        st.set_immut(name, val)

    def generate(self, st):
        name = self.children[0].value
        if name not in st.table:
            st.offset += 4
            v = Variable.make_number(0)
            v.shift = st.offset
            v.immut = True
            st.table[name] = v
            Code.append(f"  sub esp, 4 ; imut {name} [EBP-{st.table[name].shift}]")
        self.children[1].generate(st)
        v = st.get_value(name)
        Code.append(f"  mov [ebp-{v.shift}], eax")


class Assignment(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        name = self.children[0].value
        if not st.is_declared(name):
            raise Exception(f"[Semantic] Undefined variable: {name}")
        val = self.children[1].evaluate(st)
        st.set_value(name, val)

    def generate(self, st):
        self.children[1].generate(st)
        v = st.get_value(self.children[0].value)
        if v.is_param:
            Code.append(f"  mov [ebp+{v.shift}], eax")
        else:
            Code.append(f"  mov [ebp-{v.shift}], eax")


# ── I/O ───────────────────────────────────────

class Print(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        val = self.children[0].evaluate(st)
        if val.vartype == "string":   print(val.value)
        elif val.vartype == "boolean": print("true" if val.value else "false")
        elif val.vartype == "float":   print(val.to_str())
        else:                          print(val.value)

    def generate(self, st):
        self.children[0].generate(st)
        Code.append("  push eax")
        Code.append("  push format_out")
        Code.append("  call printf")
        Code.append("  add esp, 8")


class Read(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable.make_number(int(input()))

    def generate(self, st):
        Code.append("  push scan_int")
        Code.append("  push format_in")
        Code.append("  call scanf")
        Code.append("  add esp, 8")
        Code.append("  mov eax, [scan_int]")


# ── Control flow ──────────────────────────────

class Block(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        child_st = SymbolTable(parent=st)
        for c in self.children:
            result = c.evaluate(child_st)
            if result is not None:
                return result
        return None

    def generate(self, st):
        for c in self.children:
            c.generate(st)


class NoOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return None

    def generate(self, st):
        pass


class If(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        cond = self.children[0].evaluate(st)
        if cond.vartype != "boolean":
            raise Exception("[Semantic] 'if' condition must be boolean")
        if cond.truthy():
            return self.children[1].evaluate(st)
        elif len(self.children) > 2:
            return self.children[2].evaluate(st)
        return None

    def generate(self, st):
        uid = self.uid
        self.children[0].generate(st)
        Code.append("  cmp eax, 0")
        if len(self.children) == 2:
            Code.append(f"  je exit_{uid}")
            self.children[1].generate(st)
            Code.append(f"exit_{uid}:")
        else:
            Code.append(f"  je else_{uid}")
            self.children[1].generate(st)
            Code.append(f"  jmp exit_{uid}")
            Code.append(f"else_{uid}:")
            self.children[2].generate(st)
            Code.append(f"exit_{uid}:")


class IfExpr(Node):
    """Inline: if cond then expr else expr end"""
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        if self.children[0].evaluate(st).truthy():
            return self.children[1].evaluate(st)
        return self.children[2].evaluate(st)

    def generate(self, st):
        uid = self.uid
        self.children[0].generate(st)
        Code.append("  cmp eax, 0")
        Code.append(f"  je else_{uid}")
        self.children[1].generate(st)
        Code.append(f"  jmp exit_{uid}")
        Code.append(f"else_{uid}:")
        self.children[2].generate(st)
        Code.append(f"exit_{uid}:")


class While(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        while True:
            cond = self.children[0].evaluate(st)
            if cond.vartype != "boolean":
                raise Exception("[Semantic] 'while' condition must be boolean")
            if not cond.truthy(): break
            result = self.children[1].evaluate(st)
            if result is not None: return result
        return None

    def generate(self, st):
        uid = self.uid
        Code.append(f"loop_{uid}:")
        self.children[0].generate(st)
        Code.append("  cmp eax, 0")
        Code.append(f"  je exit_{uid}")
        self.children[1].generate(st)
        Code.append(f"  jmp loop_{uid}")
        Code.append(f"exit_{uid}:")


class ForNode(Node):
    """for varName = start, limit [, step] do body end"""
    def __init__(self, value, children):
        super().__init__(value, children)  # value = varName

    def evaluate(self, st):
        start = self.children[0].evaluate(st).value
        limit = self.children[1].evaluate(st).value
        if len(self.children) == 4:
            step = self.children[2].evaluate(st).value
            body = self.children[3]
        else:
            step = 1
            body = self.children[2]
        if step == 0:
            raise Exception("[Semantic] 'for' step cannot be zero")
        i = start
        while (step > 0 and i <= limit) or (step < 0 and i >= limit):
            st.set_value(self.value, Variable.make_number(i))
            body.evaluate(st)
            i += step
        st.set_value(self.value, Variable.make_number(i))
        return None

    def generate(self, st):
        var_name = self.value
        if var_name not in st.table:
            st.offset += 4
            v = Variable.make_number(0)
            v.shift = st.offset
            st.table[var_name] = v
            Code.append(f"  sub esp, 4 ; for {var_name} [EBP-{v.shift}]")
        var_shift = st.table[var_name].shift

        self.children[0].generate(st)  # start → EAX
        Code.append(f"  mov [ebp-{var_shift}], eax")

        uid = self.uid
        if len(self.children) == 4:
            step_node = self.children[2]
            body      = self.children[3]
        else:
            step_node = None
            body      = self.children[2]

        Code.append(f"loop_{uid}:")
        self.children[1].generate(st)  # limit → EAX
        Code.append("  push eax")
        Code.append(f"  mov eax, [ebp-{var_shift}]")
        Code.append("  pop ecx")
        Code.append("  cmp eax, ecx")
        Code.append("  mov eax, 0")
        Code.append("  mov ecx, 1")
        Code.append("  cmovle eax, ecx")
        Code.append("  cmp eax, 0")
        Code.append(f"  je exit_{uid}")
        body.generate(st)
        if step_node:
            step_node.generate(st)
            Code.append("  push eax")
            Code.append(f"  mov eax, [ebp-{var_shift}]")
            Code.append("  pop ecx")
            Code.append("  add eax, ecx")
        else:
            Code.append(f"  mov eax, [ebp-{var_shift}]")
            Code.append("  add eax, 1")
        Code.append(f"  mov [ebp-{var_shift}], eax")
        Code.append(f"  jmp loop_{uid}")
        Code.append(f"exit_{uid}:")


class RepeatNode(Node):
    """repeat body until cond"""
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        while True:
            self.children[0].evaluate(st)
            if self.children[1].evaluate(st).truthy():
                break
        return None

    def generate(self, st):
        uid = self.uid
        Code.append(f"loop_{uid}:")
        self.children[0].generate(st)
        self.children[1].generate(st)
        Code.append("  cmp eax, 0")
        Code.append(f"  je loop_{uid}")


# ── Functions ─────────────────────────────────

# Global function registry (mirrors Go's globalFuncTable)
_global_func_table = {}

# Sentinel used to propagate return values up the call stack
class _ReturnException(Exception):
    def __init__(self, val: Variable):
        self.val = val


class FuncDec(Node):
    """
    value      = return type (str or None for void)
    children[0]    = Identifier (name)
    children[1..n] = VarDec (parameters)
    children[-1]   = Block (body)
    """
    def __init__(self, value, children):
        super().__init__(value, children)
        self.params      = []    # param names
        self.param_types = []    # param types (or "" for untyped)
        self.ret_type    = value if value else ""
        self.def_scope   = None  # captured at evaluation time

    def evaluate(self, st):
        self.def_scope = st
        func_name = self.children[0].value
        _global_func_table[func_name] = self
        st.create_variable(func_name, self.ret_type or "void", is_func=True)
        st.set_value(func_name, Variable("function", self))

    def generate(self, st):
        func_name = self.children[0].value
        _global_func_table[func_name] = self

        old_buf = Code.current
        Code.current = Code.func_instructions

        # Build param symbol table: [EBP+8], [EBP+12], ...
        func_st = SymbolTable()
        for i, param_node in enumerate(self.children[1:-1]):
            param_name = param_node.children[0].value
            v = Variable.make_number(0)
            v.shift    = 8 + i * 4
            v.is_param = True
            func_st.table[param_name] = v

        Code.append(f"func_{func_name}:")
        Code.append("  push ebp")
        Code.append("  mov ebp, esp")
        self.children[-1].generate(func_st)
        Code.append("  mov esp, ebp")
        Code.append("  pop ebp")
        Code.append("  ret")

        Code.current = old_buf


class FuncCall(Node):
    """
    value    = function name (str)
    children = argument expressions
    """
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        func_name = self.value

        # Look up function
        func_var = None
        try:
            func_var = st.get_value(func_name)
        except Exception:
            pass

        func_dec = None
        if func_var and func_var.vartype == "function":
            func_dec = func_var.value
        elif func_name in _global_func_table:
            func_dec = _global_func_table[func_name]

        if func_dec is None:
            raise Exception(f"[Semantic] Undefined function: {func_name}")

        # Parameters: children[1:-1] of FuncDec
        param_nodes = func_dec.children[1:-1]
        arg_nodes   = self.children

        if len(arg_nodes) != len(param_nodes):
            raise Exception(
                f"[Semantic] Function '{func_name}' expects {len(param_nodes)} args "
                f"but got {len(arg_nodes)}"
            )

        # Evaluate arguments in caller scope
        evaluated_args = [a.evaluate(st) for a in arg_nodes]

        # Create function scope chained to definition scope
        if func_dec.def_scope:
            func_st = SymbolTable(parent=func_dec.def_scope)
        else:
            func_st = SymbolTable()
        func_st.inside_function = True

        # Bind parameters
        for param_node, val in zip(param_nodes, evaluated_args):
            param_name = param_node.children[0].value
            param_type = param_node.value  # the declared type
            if param_type and val.vartype != param_type:
                raise Exception(
                    f"[Semantic] Function '{func_name}' param '{param_name}' "
                    f"expects {param_type} but got {val.vartype}"
                )
            func_st.table[param_name] = Variable(val.vartype, val.value)

        # Execute body, catching _ReturnException
        result = None
        try:
            func_dec.children[-1].evaluate(func_st)
        except _ReturnException as r:
            result = r.val

        # Type-check return
        ret_type = func_dec.value
        if ret_type and ret_type != "void":
            if result is None:
                raise Exception(
                    f"[Semantic] Function '{func_name}' must return a value of type {ret_type}"
                )
            if result.vartype != ret_type:
                raise Exception(
                    f"[Semantic] Function '{func_name}' must return {ret_type} "
                    f"but returned {result.vartype}"
                )
            return result
        return None

    def generate(self, st):
        # Push args right-to-left
        for arg in reversed(self.children):
            arg.generate(st)
            Code.append("  push eax")
        Code.append(f"  call func_{self.value}")
        if self.children:
            Code.append(f"  add esp, {len(self.children) * 4}")


class Return(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        val = self.children[0].evaluate(st)
        raise _ReturnException(val)

    def generate(self, st):
        self.children[0].generate(st)
        Code.append("  mov esp, ebp")
        Code.append("  pop ebp")
        Code.append("  ret")


# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

# Tracks nesting depth of function definitions during parsing
_parser_function_depth = 0


class Parser:
    lexer = None

    def parse_atom() -> Node:
        tok = Parser.lexer.next

        # Inline if expression
        if tok.type == "IF":
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "THEN":
                raise Exception(f"[Parser] Expected 'then' in inline if but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            then_expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "ELSE":
                raise Exception(f"[Parser] Expected 'else' in inline if but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            else_expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "KW_END":
                raise Exception(f"[Parser] Expected 'end' to close inline if but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return IfExpr(None, [cond, then_expr, else_expr])

        if tok.type == "OPEN_PAR":
            Parser.lexer.select_next()
            result = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return result

        if tok.type == "INT":
            Parser.lexer.select_next()
            return IntVal(tok.value, [])

        if tok.type == "FLOAT_LIT":
            Parser.lexer.select_next()
            return FloatVal(float(tok.value), [])

        if tok.type == "BOOL":
            Parser.lexer.select_next()
            return BoolVal(tok.value == "true", [])

        if tok.type == "STR":
            Parser.lexer.select_next()
            return StringVal(tok.value, [])

        if tok.type == "IDEN":
            name = tok.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()  # consume '('
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in call to '{name}' but got {Parser.lexer.next.type}")
                Parser.lexer.select_next()
                return FuncCall(name, args)
            return Identifier(name, [])

        raise Exception(f"[Parser] Unexpected token {tok.type} in atom")

    def parse_power() -> Node:
        base = Parser.parse_atom()
        if Parser.lexer.next.type == "POW":
            Parser.lexer.select_next()
            return BinOp("**", [base, Parser.parse_factor()])
        return base

    def parse_factor() -> Node:
        tok = Parser.lexer.next

        if tok.type == "PLUS":
            Parser.lexer.select_next()
            return UnOp("+", [Parser.parse_factor()])

        if tok.type == "MINUS":
            Parser.lexer.select_next()
            return UnOp("-", [Parser.parse_factor()])

        # Cast: (TYPE) factor — use save/restore for lookahead
        if tok.type == "OPEN_PAR":
            saved = Parser.lexer.save()
            Parser.lexer.select_next()  # consume '('
            if Parser.lexer.next.type == "TYPE":
                cast_type = Parser.lexer.next.value
                Parser.lexer.select_next()  # consume TYPE
                if Parser.lexer.next.type == "CLOSE_PAR":
                    Parser.lexer.select_next()  # consume ')'
                    return CastNode(cast_type, [Parser.parse_factor()])
            Parser.lexer.restore(saved)

        if tok.type == "READ":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' after 'read' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' in 'read()' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return Read(None, [])

        return Parser.parse_power()

    def parse_term() -> Node:
        node = Parser.parse_factor()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = BinOp(op, [node, Parser.parse_factor()])
        return node

    def parse_expression() -> Node:
        node = Parser.parse_term()
        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = BinOp(op, [node, Parser.parse_term()])
        return node

    def parse_concat_expression() -> Node:
        left = Parser.parse_expression()
        if Parser.lexer.next.type == "CONCAT":
            Parser.lexer.select_next()
            right = Parser.parse_concat_expression()  # right-associative
            return BinOp("..", [left, right])
        return left

    def parse_rel_expression() -> Node:
        node = Parser.parse_concat_expression()
        if Parser.lexer.next.type in ("EQ", "GT", "LT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = BinOp(op, [node, Parser.parse_concat_expression()])
        return node

    def parse_not_expression() -> Node:
        if Parser.lexer.next.type == "NOT":
            Parser.lexer.select_next()
            return UnOp("not", [Parser.parse_not_expression()])
        return Parser.parse_rel_expression()

    def parse_bool_term() -> Node:
        node = Parser.parse_not_expression()
        while Parser.lexer.next.type == "AND":
            Parser.lexer.select_next()
            node = BinOp("and", [node, Parser.parse_not_expression()])
        return node

    def parse_bool_expression() -> Node:
        node = Parser.parse_bool_term()
        while Parser.lexer.next.type == "OR":
            Parser.lexer.select_next()
            node = BinOp("or", [node, Parser.parse_bool_term()])
        return node

    def parse_block() -> Node:
        children = []
        while Parser.lexer.next.type not in ("EOF", "KW_END", "ELSE", "UNTIL"):
            children.append(Parser.parse_statement())
        return Block(None, children)

    def parse_var_declaration() -> Node:
        Parser.lexer.select_next()  # consume 'local'
        if Parser.lexer.next.type != "IDEN":
            raise Exception(f"[Parser] Expected identifier after 'local' but got {Parser.lexer.next.type}")
        name = Parser.lexer.next.value
        Parser.lexer.select_next()
        if Parser.lexer.next.type != "TYPE":
            raise Exception(f"[Parser] Expected type after identifier in 'local' but got {Parser.lexer.next.type}")
        vartype = Parser.lexer.next.value
        Parser.lexer.select_next()
        children = [Identifier(name, [])]
        if Parser.lexer.next.type == "ASSIGN":
            Parser.lexer.select_next()
            children.append(Parser.parse_bool_expression())
        if Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
        return VarDec(vartype, children)

    def parse_func_declaration() -> Node:
        global _parser_function_depth
        if _parser_function_depth > 0:
            raise Exception("[Parser] Unexpected 'function' definition inside function body")

        Parser.lexer.select_next()  # consume 'function'
        if Parser.lexer.next.type != "IDEN":
            raise Exception(f"[Parser] Expected function name but got {Parser.lexer.next.type}")
        func_name = Parser.lexer.next.value
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "OPEN_PAR":
            raise Exception(f"[Parser] Expected '(' after function name but got {Parser.lexer.next.type}")
        Parser.lexer.select_next()

        params = []
        if Parser.lexer.next.type != "CLOSE_PAR":
            if Parser.lexer.next.type != "IDEN":
                raise Exception(f"[Parser] Expected parameter name but got {Parser.lexer.next.type}")
            pname = Parser.lexer.next.value
            Parser.lexer.select_next()
            ptype = ""
            if Parser.lexer.next.type == "TYPE":
                ptype = Parser.lexer.next.value
                Parser.lexer.select_next()
            params.append(VarDec(ptype, [Identifier(pname, [])]))

            while Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "IDEN":
                    raise Exception(f"[Parser] Expected parameter name but got {Parser.lexer.next.type}")
                pname = Parser.lexer.next.value
                Parser.lexer.select_next()
                ptype = ""
                if Parser.lexer.next.type == "TYPE":
                    ptype = Parser.lexer.next.value
                    Parser.lexer.select_next()
                params.append(VarDec(ptype, [Identifier(pname, [])]))

        if Parser.lexer.next.type != "CLOSE_PAR":
            raise Exception(f"[Parser] Expected ')' in function definition but got {Parser.lexer.next.type}")
        Parser.lexer.select_next()

        ret_type = None
        if Parser.lexer.next.type == "TYPE":
            ret_type = Parser.lexer.next.value
            Parser.lexer.select_next()

        if Parser.lexer.next.type == "END":
            Parser.lexer.select_next()

        _parser_function_depth += 1
        body = Parser.parse_block()
        _parser_function_depth -= 1

        if Parser.lexer.next.type != "KW_END":
            raise Exception(f"[Parser] Expected 'end' to close function but got {Parser.lexer.next.type}")
        Parser.lexer.select_next()
        if Parser.lexer.next.type == "END":
            Parser.lexer.select_next()

        children = [Identifier(func_name, [])] + params + [body]
        return FuncDec(ret_type, children)

    def parse_statement() -> Node:
        tok = Parser.lexer.next

        if tok.type == "END":
            Parser.lexer.select_next()
            return NoOp(None, [])

        if tok.type == "VAR":
            return Parser.parse_var_declaration()

        if tok.type == "IMUT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception(f"[Parser] Expected identifier after 'imut' but got {Parser.lexer.next.type}")
            name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception(f"[Parser] Expected '=' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return ImutAssignment(None, [Identifier(name, []), expr])

        if tok.type == "IDEN":
            name = tok.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()  # consume '('
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in call to '{name}' but got {Parser.lexer.next.type}")
                Parser.lexer.select_next()
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
                return FuncCall(name, args)
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception(f"[Parser] Expected '=' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return Assignment(None, [Identifier(name, []), expr])

        if tok.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return Print(None, [expr])

        if tok.type == "DO":
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            block = Parser.parse_block()
            if Parser.lexer.next.type != "KW_END":
                raise Exception(f"[Parser] Expected 'end' to close 'do' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return block

        if tok.type == "IF":
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "THEN":
                raise Exception(f"[Parser] Expected 'then' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline after 'then' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            then_block = Parser.parse_block()
            children = [cond, then_block]
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "END":
                    raise Exception(f"[Parser] Expected newline after 'else' but got {Parser.lexer.next.type}")
                Parser.lexer.select_next()
                children.append(Parser.parse_block())
            if Parser.lexer.next.type != "KW_END":
                raise Exception(f"[Parser] Expected 'end' to close 'if' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return If(None, children)

        if tok.type == "WHILE":
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "DO":
                raise Exception(f"[Parser] Expected 'do' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline after 'do' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "KW_END":
                raise Exception(f"[Parser] Expected 'end' to close 'while' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return While(None, [cond, body])

        if tok.type == "FOR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception(f"[Parser] Expected identifier after 'for' but got {Parser.lexer.next.type}")
            var_name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception(f"[Parser] Expected '=' in 'for' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            start = Parser.parse_expression()
            if Parser.lexer.next.type != "COMMA":
                raise Exception(f"[Parser] Expected ',' after start in 'for' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            limit = Parser.parse_expression()
            for_children = [start, limit]
            if Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                for_children.append(Parser.parse_expression())
            if Parser.lexer.next.type != "DO":
                raise Exception(f"[Parser] Expected 'do' in 'for' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline after 'do' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "KW_END":
                raise Exception(f"[Parser] Expected 'end' to close 'for' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            for_children.append(body)
            return ForNode(var_name, for_children)

        if tok.type == "REPEAT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline after 'repeat' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "UNTIL":
                raise Exception(f"[Parser] Expected 'until' to close 'repeat' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return RepeatNode(None, [body, cond])

        if tok.type == "RETURN":
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return Return(None, [expr])

        if tok.type == "FUNCTION":
            return Parser.parse_func_declaration()

        raise Exception(f"[Parser] Unexpected token {tok.type}")

    def parse_program() -> Node:
        children = []
        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
        while Parser.lexer.next.type != "EOF":
            children.append(Parser.parse_statement())
            while Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
        return Block(None, children)

    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        node = Parser.parse_program()
        if Parser.lexer.next.type != "EOF":
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected EOF")
        return node


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <source.lua>")
        sys.exit(1)

    filename = sys.argv[1]
    with open(filename, "r") as f:
        code = f.read() + "\n"

    code = PrePro.filter(code)
    ast  = Parser.run(code)

    st = SymbolTable()
    ast.evaluate(st)


if __name__ == "__main__":
    main()