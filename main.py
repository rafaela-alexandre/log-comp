import sys
import re
import os

# ─────────────────────────────────────────────
#  TOKEN
# ─────────────────────────────────────────────

class Token:
    def __init__(self, type: str, value):
        self.type = type
        self.value = value


# ─────────────────────────────────────────────
#  PRE-PROCESSOR
# ─────────────────────────────────────────────

class PrePro:
    def filter(code: str) -> str:
        return re.sub(r'--[^\n]*', '', code)


# ─────────────────────────────────────────────
#  VARIABLE & SYMBOL TABLE
# ─────────────────────────────────────────────

class Variable:
    def __init__(self, vartype: str, value=None, shift: int = 0, is_param: bool = False):
        self.vartype  = vartype   # "number", "float", "string", "boolean"
        self.value    = value
        self.shift    = shift     # deslocamento relativo ao EBP
        self.is_param = is_param  # se True, acessa via [EBP+shift]


class SymbolTable:
    def __init__(self):
        self.table  = {}
        self.offset = 0

    def create_variable(self, name: str, vartype: str):
        if name in self.table:
            raise Exception(f"[Semantic] Variable '{name}' already declared")
        self.offset += 4
        default = {"number": 0, "float": 0.0, "string": "", "boolean": False}.get(vartype, 0)
        self.table[name] = Variable(vartype, default, self.offset)

    def get_value(self, name: str):
        if name not in self.table:
            raise Exception(f"[Semantic] Variable '{name}' not defined")
        return self.table[name].value

    def set_value(self, name: str, value, vartype: str = None):
        if name not in self.table:
            raise Exception(f"[Semantic] Variable '{name}' not defined")
        var = self.table[name]
        if vartype is not None and var.vartype != vartype:
            raise Exception(
                f"[Semantic] Type mismatch for '{name}': expected {var.vartype}, got {vartype}"
            )
        var.value = value


# ─────────────────────────────────────────────
#  CODE
# ─────────────────────────────────────────────

class Code:
    instructions      = []
    func_instructions = []
    _current          = "main"   # "main" ou "func"

    def append(code: str) -> None:
        if Code._current == "func":
            Code.func_instructions.append(code)
        else:
            Code.instructions.append(code)

    def dump(filename: str) -> None:
        header = (
            'section .data\n'
            '  format_out: db "%d", 10, 0 ; format do printf\n'
            '  format_in: db "%d", 0 ; format do scanf\n'
            '  scan_int: dd 0; 32-bits integer\n'
            '\n'
            'section .text\n'
            '\n'
            '  extern printf ; usar _printf para Windows\n'
            '  extern scanf ; usar _scanf para Windows\n'
            '  ; extern _ExitProcess@4 ; usar para Windows\n'
            '  global _start ; inicio do programa\n'
            '\n'
            '_start:\n'
            '  push ebp ; guarda o EBP\n'
            '  mov ebp, esp ; zera a pilha\n'
            '\n'
            '  ; aqui comeca o codigo gerado:\n'
            '\n'
        )
        footer = (
            '\n'
            '  ; aqui termina o codigo gerado\n'
            '\n'
            '  mov esp, ebp ; reestabelece a pilha\n'
            '  pop ebp\n'
            '\n'
            '  ; chamada da interrupcao de saida (Linux)\n'
            '  mov eax, 1\n'
            '  xor ebx, ebx\n'
            '  int 0x80\n'
            '  ; Para Windows:\n'
            '  ; push dword 0\n'
            '  ; call _ExitProcess@4\n'
        )
        with open(filename, 'w') as f:
            f.write(header)
            f.write("\n".join(Code.instructions))
            f.write(footer)
            if Code.func_instructions:
                f.write("\n")
                f.write("\n".join(Code.func_instructions))
                f.write("\n")


# ─────────────────────────────────────────────
#  LEXER
# ─────────────────────────────────────────────

class Lexer:
    def __init__(self, source: str):
        self.source   = source
        self.position = 0
        self.next     = None

    RESERVED = {
        "print":    "PRINT",
        "if":       "IF",
        "else":     "ELSE",
        "while":    "WHILE",
        "do":       "OPEN_BRA",
        "end":      "CLOSE_BRA",
        "then":     "OPEN_IF_BRA",
        "and":      "AND",
        "or":       "OR",
        "not":      "NOT",
        "read":     "READ",
        "local":    "VAR",
        "true":     "BOOL",
        "false":    "BOOL",
        "number":   "TYPE",
        "string":   "TYPE",
        "boolean":  "TYPE",
        "float":    "TYPE",
        "for":      "FOR",
        "repeat":   "REPEAT",
        "until":    "UNTIL",
        "function": "FUNCTION",
        "return":   "RETURN",
    }

    def select_next(self):
        while self.position < len(self.source) and self.source[self.position] in (' ', '\t', '\r'):
            self.position += 1

        if self.position >= len(self.source):
            self.next = Token("EOF", "")
            return

        char = self.source[self.position]

        if char == "\n":
            self.next = Token("END", "\n")
            self.position += 1

        elif char == "+":
            self.next = Token("PLUS", "+")
            self.position += 1

        elif char == "-":
            self.next = Token("MINUS", "-")
            self.position += 1

        elif char == "*":
            if self.position + 1 < len(self.source) and self.source[self.position + 1] == "*":
                self.next = Token("POW", "**")
                self.position += 2
            else:
                self.next = Token("MULT", "*")
                self.position += 1

        elif char == "/":
            self.next = Token("DIV", "/")
            self.position += 1

        elif char == "(":
            self.next = Token("OPEN_PAR", "(")
            self.position += 1

        elif char == ")":
            self.next = Token("CLOSE_PAR", ")")
            self.position += 1

        elif char == ",":
            self.next = Token("COMMA", ",")
            self.position += 1

        elif char == ".":
            if self.position + 1 < len(self.source) and self.source[self.position + 1] == ".":
                self.next = Token("CONCAT", "..")
                self.position += 2
            else:
                raise Exception(f"[Lexer] Invalid symbol '.' at position {self.position}")

        elif char == "=":
            if self.position + 1 < len(self.source) and self.source[self.position + 1] == "=":
                self.next = Token("EQ", "==")
                self.position += 2
            else:
                self.next = Token("ASSIGN", "=")
                self.position += 1

        elif char == "<":
            self.next = Token("LT", "<")
            self.position += 1

        elif char == ">":
            self.next = Token("GT", ">")
            self.position += 1

        elif char == '"':
            self.position += 1
            s = ""
            while self.position < len(self.source) and self.source[self.position] != '"':
                s += self.source[self.position]
                self.position += 1
            if self.position >= len(self.source):
                raise Exception("[Lexer] Unclosed string literal")
            self.position += 1
            self.next = Token("STR", s)

        elif char.isdigit():
            num = ""
            while self.position < len(self.source) and self.source[self.position].isdigit():
                num += self.source[self.position]
                self.position += 1
            # float: digito '.' digito (mas nao '..')
            if (self.position < len(self.source) and self.source[self.position] == '.' and
                    not (self.position + 1 < len(self.source) and self.source[self.position + 1] == '.')):
                num += '.'
                self.position += 1
                while self.position < len(self.source) and self.source[self.position].isdigit():
                    num += self.source[self.position]
                    self.position += 1
                self.next = Token("FLOAT_LIT", float(num))
            else:
                self.next = Token("INT", int(num))

        elif char.isalpha() or char == "_":
            iden = ""
            while self.position < len(self.source) and (
                self.source[self.position].isalnum() or self.source[self.position] == "_"
            ):
                iden += self.source[self.position]
                self.position += 1
            tt = Lexer.RESERVED.get(iden, "IDEN")
            if tt == "BOOL":
                self.next = Token("BOOL", iden == "true")
            else:
                self.next = Token(tt, iden)

        else:
            raise Exception(f"[Lexer] Invalid symbol '{char}' at position {self.position}")


# ─────────────────────────────────────────────
#  AST NODES
# ─────────────────────────────────────────────

# tabela global de funcoes
_func_table = {}

# excecao para propagar return
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value


class Node:
    id = 0

    @staticmethod
    def new_id() -> int:
        Node.id += 1
        return Node.id

    def __init__(self, value, children=None):
        self.value    = value
        self.children = children if children is not None else []
        self.uid      = Node.new_id()

    def evaluate(self, st: SymbolTable):
        raise NotImplementedError("[Semantic] evaluate() not implemented")

    def generate(self, st: SymbolTable):
        raise NotImplementedError("[CodeGen] generate() not implemented")


class IntVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("number", self.value)

    def generate(self, st):
        Code.append(f"  mov eax, {self.value}")


class FloatVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("float", self.value)

    def generate(self, st):
        raise Exception("[CodeGen] float not supported in assembly generation")


class BoolVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("boolean", self.value)

    def generate(self, st):
        Code.append(f"  mov eax, {1 if self.value else 0}")


class StringVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("string", self.value)

    def generate(self, st):
        pass  # strings nao geram codigo assembly


class Identifier(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return st.table[self.value] if self.value in st.table else (_ for _ in ()).throw(
            Exception(f"[Semantic] Variable '{self.value}' not defined"))

    def evaluate(self, st):
        if self.value not in st.table:
            raise Exception(f"[Semantic] Variable '{self.value}' not defined")
        return st.table[self.value]

    def generate(self, st):
        if self.value not in st.table:
            raise Exception(f"[Semantic] Variable '{self.value}' not defined")
        var = st.table[self.value]
        if var.is_param:
            Code.append(f"  mov eax, [ebp+{var.shift}] ; {self.value}")
        else:
            Code.append(f"  mov eax, [ebp-{var.shift}] ; {self.value}")


class UnOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        child = self.children[0].evaluate(st)
        if self.value == "+":
            if child.vartype not in ("number", "float"):
                raise Exception("[Semantic] Unary '+' requires number or float")
            return Variable(child.vartype, child.value)
        elif self.value == "-":
            if child.vartype not in ("number", "float"):
                raise Exception("[Semantic] Unary '-' requires number or float")
            return Variable(child.vartype, -child.value)
        elif self.value == "not":
            if child.vartype != "boolean":
                raise Exception("[Semantic] 'not' requires boolean")
            return Variable("boolean", not child.value)
        raise Exception(f"[Semantic] Unknown unary operator '{self.value}'")

    def generate(self, st):
        self.children[0].generate(st)
        if self.value == "-":
            Code.append("  neg eax")
        elif self.value == "not":
            Code.append("  xor eax, 1")


class BinOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        left  = self.children[0].evaluate(st)
        right = self.children[1].evaluate(st)
        op    = self.value

        if op == "or":
            if left.vartype != "boolean" or right.vartype != "boolean":
                raise Exception("[Semantic] 'or' requires booleans")
            return Variable("boolean", left.value or right.value)

        if op == "and":
            if left.vartype != "boolean" or right.vartype != "boolean":
                raise Exception("[Semantic] 'and' requires booleans")
            return Variable("boolean", left.value and right.value)

        if op == "..":
            def to_str(v):
                if v.vartype == "string": return v.value
                if v.vartype == "boolean": return "true" if v.value else "false"
                return str(v.value)
            return Variable("string", to_str(left) + to_str(right))

        if op in ("==", "<", ">"):
            lv = left.value if left.vartype != "float" else left.value
            rv = right.value if right.vartype != "float" else right.value
            if op == "==": res = lv == rv
            elif op == "<": res = lv < rv
            else:           res = lv > rv
            return Variable("boolean", res)

        if op == "**":
            if left.vartype not in ("number", "float") or right.vartype not in ("number", "float"):
                raise Exception("[Semantic] '**' requires numbers")
            result = left.value ** right.value
            vtype = "float" if (left.vartype == "float" or right.vartype == "float") else "number"
            return Variable(vtype, result)

        if left.vartype == "string" or right.vartype == "string":
            if op == "+":
                return Variable("string", str(left.value) + str(right.value))
            raise Exception(f"[Semantic] Operator '{op}' not valid for strings")

        if left.vartype not in ("number", "float") or right.vartype not in ("number", "float"):
            raise Exception(f"[Semantic] Operator '{op}' requires numbers")

        is_float = left.vartype == "float" or right.vartype == "float"
        vtype = "float" if is_float else "number"
        lv = float(left.value) if is_float else left.value
        rv = float(right.value) if is_float else right.value

        if op == "+": return Variable(vtype, lv + rv)
        if op == "-": return Variable(vtype, lv - rv)
        if op == "*": return Variable(vtype, lv * rv)
        if op == "/":
            if rv == 0: raise Exception("[Semantic] Division by zero")
            return Variable(vtype, lv // rv if not is_float else lv / rv)

        raise Exception(f"[Semantic] Unknown binary operator '{op}'")

    def generate(self, st):
        op = self.value

        if op == "or":
            self.children[0].generate(st)
            Code.append("  push eax")
            self.children[1].generate(st)
            Code.append("  pop ecx")
            Code.append("  or eax, ecx ; or")
            Code.append("  cmp eax, 0")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmovne eax, ecx")
            return

        if op == "and":
            self.children[0].generate(st)
            Code.append("  push eax")
            self.children[1].generate(st)
            Code.append("  pop ecx")
            Code.append("  and eax, ecx ; and")
            Code.append("  cmp eax, 0")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmovne eax, ecx")
            return

        if op in ("..", "**", "float"):
            raise Exception(f"[CodeGen] operator '{op}' not supported in assembly generation")

        # right primeiro, empilha; left em EAX
        self.children[1].generate(st)
        Code.append("  push eax")
        self.children[0].generate(st)

        if op == "+":
            Code.append("  pop ecx")
            Code.append("  add eax, ecx")
        elif op == "-":
            Code.append("  pop ecx")
            Code.append("  sub eax, ecx")
        elif op == "*":
            Code.append("  pop ecx")
            Code.append("  imul ecx")
        elif op == "/":
            Code.append("  pop ecx")
            Code.append("  cdq")
            Code.append("  idiv ecx")
        elif op == "==":
            Code.append("  pop ecx")
            Code.append("  cmp eax, ecx")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmove eax, ecx ; ==")
        elif op == "<":
            Code.append("  pop ecx")
            Code.append("  cmp eax, ecx")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmovl eax, ecx ; <")
        elif op == ">":
            Code.append("  pop ecx")
            Code.append("  cmp eax, ecx")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmovg eax, ecx ; >")


class VarDec(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        name = self.children[0].value
        st.create_variable(name, self.value)
        if len(self.children) > 1:
            result = self.children[1].evaluate(st)
            st.set_value(name, result.value, result.vartype)

    def generate(self, st):
        name = self.children[0].value
        st.create_variable(name, self.value)
        var = st.table[name]
        Code.append(f"  sub esp, 4 ; var {name} {self.value} [EBP-{var.shift}]")
        if len(self.children) > 1:
            self.children[1].generate(st)
            Code.append(f"  mov [ebp-{var.shift}], eax ; {name} = init")


class Assignment(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        result = self.children[1].evaluate(st)
        st.set_value(self.children[0].value, result.value, result.vartype)

    def generate(self, st):
        self.children[1].generate(st)
        var = st.table[self.children[0].value]
        if var.is_param:
            Code.append(f"  mov [ebp+{var.shift}], eax ; {self.children[0].value} = ...")
        else:
            Code.append(f"  mov [ebp-{var.shift}], eax ; {self.children[0].value} = ...")


class Print(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        result = self.children[0].evaluate(st)
        if result.vartype == "boolean":
            print("true" if result.value else "false")
        else:
            print(result.value)

    def generate(self, st):
        self.children[0].generate(st)
        Code.append("  push eax ; arg printf")
        Code.append("  push format_out")
        Code.append("  call printf")
        Code.append("  add esp, 8 ; limpa args")


class Read(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("number", int(input()))

    def generate(self, st):
        Code.append("  push scan_int ; endereco de suporte")
        Code.append("  push format_in ; formato de entrada (int)")
        Code.append("  call scanf")
        Code.append("  add esp, 8 ; Remove os argumentos da pilha")
        Code.append("  mov eax, dword [scan_int] ; retorna o valor lido em EAX")


class If(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        cond = self.children[0].evaluate(st)
        if cond.value:
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)

    def generate(self, st):
        uid = self.uid
        self.children[0].generate(st)
        Code.append(f"  cmp eax, 0")
        if len(self.children) > 2:
            Code.append(f"  je else_{uid}")
        else:
            Code.append(f"  je exit_{uid}")
        self.children[1].generate(st)
        if len(self.children) > 2:
            Code.append(f"  jmp exit_{uid}")
            Code.append(f"  else_{uid}:")
            self.children[2].generate(st)
        Code.append(f"  exit_{uid}:")


class While(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        while True:
            cond = self.children[0].evaluate(st)
            if not cond.value:
                break
            self.children[1].evaluate(st)

    def generate(self, st):
        uid = self.uid
        Code.append(f"  loop_{uid}: ; label do loop")
        self.children[0].generate(st)
        Code.append(f"  cmp eax, 0 ; se a condicao for falsa, sai")
        Code.append(f"  je exit_{uid}")
        self.children[1].generate(st)
        Code.append(f"  jmp loop_{uid}")
        Code.append(f"  exit_{uid}:")


class For(Node):
    """children: [start, limit, body] ou [start, limit, step, body]; value = varname"""
    def __init__(self, value, children):
        super().__init__(value, children)

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
        # declara a variavel de controle se nao existir
        if self.value not in st.table:
            st.table[self.value] = Variable("number", start)
        i = start
        while (step > 0 and i <= limit) or (step < 0 and i >= limit):
            st.set_value(self.value, i)
            body.evaluate(st)
            i += step
        st.set_value(self.value, i)

    def generate(self, st):
        var_name = self.value
        if var_name not in st.table:
            st.offset += 4
            st.table[var_name] = Variable("number", 0, st.offset)
            Code.append(f"  sub esp, 4 ; for {var_name} [EBP-{st.offset}]")
        var_shift = st.table[var_name].shift

        self.children[0].generate(st)  # start -> EAX
        Code.append(f"  mov [ebp-{var_shift}], eax")

        uid = self.uid
        if len(self.children) == 4:
            step_node = self.children[2]
            body      = self.children[3]
        else:
            step_node = None
            body      = self.children[2]

        Code.append(f"  loop_{uid}:")
        self.children[1].generate(st)  # limit -> EAX
        Code.append(f"  push eax")
        Code.append(f"  mov eax, [ebp-{var_shift}]")
        Code.append(f"  pop ecx")
        Code.append(f"  cmp eax, ecx")
        Code.append(f"  mov eax, 0")
        Code.append(f"  mov ecx, 1")
        Code.append(f"  cmovle eax, ecx ; i <= limit")
        Code.append(f"  cmp eax, 0")
        Code.append(f"  je exit_{uid}")

        body.generate(st)

        if step_node:
            step_node.generate(st)
            Code.append(f"  push eax")
            Code.append(f"  mov eax, [ebp-{var_shift}]")
            Code.append(f"  pop ecx")
            Code.append(f"  add eax, ecx")
        else:
            Code.append(f"  mov eax, [ebp-{var_shift}]")
            Code.append(f"  add eax, 1")
        Code.append(f"  mov [ebp-{var_shift}], eax")
        Code.append(f"  jmp loop_{uid}")
        Code.append(f"  exit_{uid}:")


class Repeat(Node):
    """children: [body, condition]"""
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        while True:
            self.children[0].evaluate(st)
            if self.children[1].evaluate(st).value:
                break

    def generate(self, st):
        uid = self.uid
        Code.append(f"  loop_{uid}:")
        self.children[0].generate(st)  # body
        self.children[1].generate(st)  # condition -> EAX
        Code.append(f"  cmp eax, 0")
        Code.append(f"  je loop_{uid}")


class FuncDef(Node):
    """value = nome; children[0] = Block; children[1..] = params (Identifier)"""
    def __init__(self, value, children, params=None):
        super().__init__(value, children)
        self.params = params or []

    def evaluate(self, st):
        _func_table[self.value] = self

    def generate(self, st):
        _func_table[self.value] = self
        old = Code._current
        Code._current = "func"

        func_st = SymbolTable()
        for i, param in enumerate(self.params):
            v = Variable("number", 0, 8 + i * 4, is_param=True)
            func_st.table[param] = v

        Code.append(f"  func_{self.value}:")
        Code.append(f"  push ebp")
        Code.append(f"  mov ebp, esp")
        self.children[0].generate(func_st)
        Code.append(f"  mov esp, ebp")
        Code.append(f"  pop ebp")
        Code.append(f"  ret")

        Code._current = old


class FuncCall(Node):
    """value = nome; children = args"""
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        if self.value not in _func_table:
            raise Exception(f"[Semantic] Undefined function: {self.value}")
        defn = _func_table[self.value]
        if len(self.children) != len(defn.params):
            raise Exception(f"[Semantic] Function '{self.value}' expects {len(defn.params)} args")
        func_st = SymbolTable()
        for param, arg_node in zip(defn.params, self.children):
            val = arg_node.evaluate(st)
            func_st.table[param] = Variable(val.vartype, val.value)
        try:
            defn.children[0].evaluate(func_st)
            return Variable("number", 0)
        except ReturnException as e:
            return e.value

    def generate(self, st):
        # empilha args da direita para esquerda
        for arg in reversed(self.children):
            arg.generate(st)
            Code.append("  push eax")
        Code.append(f"  call func_{self.value}")
        if self.children:
            Code.append(f"  add esp, {len(self.children) * 4} ; limpa args")


class ReturnNode(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        val = self.children[0].evaluate(st)
        raise ReturnException(val)

    def generate(self, st):
        self.children[0].generate(st)
        Code.append("  mov esp, ebp")
        Code.append("  pop ebp")
        Code.append("  ret")


class Block(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        for child in self.children:
            child.evaluate(st)

    def generate(self, st):
        for child in self.children:
            child.generate(st)


class NoOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        pass

    def generate(self, st):
        pass


# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

class Parser:
    lexer = None

    def parse_factor() -> Node:
        tok = Parser.lexer.next

        if tok.type == "PLUS":
            Parser.lexer.select_next()
            return UnOp("+", [Parser.parse_factor()])

        elif tok.type == "MINUS":
            Parser.lexer.select_next()
            return UnOp("-", [Parser.parse_factor()])

        elif tok.type == "NOT":
            Parser.lexer.select_next()
            return UnOp("not", [Parser.parse_factor()])

        elif tok.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return node

        elif tok.type == "INT":
            Parser.lexer.select_next()
            return IntVal(tok.value, [])

        elif tok.type == "FLOAT_LIT":
            Parser.lexer.select_next()
            return FloatVal(tok.value, [])

        elif tok.type == "BOOL":
            Parser.lexer.select_next()
            return BoolVal(tok.value, [])

        elif tok.type == "STR":
            Parser.lexer.select_next()
            return StringVal(tok.value, [])

        elif tok.type == "READ":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception("[Parser] Expected '(' after read")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception("[Parser] Expected ')' after read(")
            Parser.lexer.select_next()
            return Read(None, [])

        elif tok.type == "IDEN":
            name = tok.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in call to '{name}'")
                Parser.lexer.select_next()
                return FuncCall(name, args)
            return Identifier(name, [])

        else:
            raise Exception(f"[Parser] Unexpected token '{tok.type}' ({tok.value!r}), expected factor")

    def parse_power() -> Node:
        base = Parser.parse_factor()
        if Parser.lexer.next.type == "POW":
            Parser.lexer.select_next()
            return BinOp("**", [base, Parser.parse_factor()])
        return base

    def parse_term() -> Node:
        node = Parser.parse_power()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = BinOp(op, [node, Parser.parse_power()])
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
        if Parser.lexer.next.type in ("EQ", "LT", "GT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = BinOp(op, [node, Parser.parse_concat_expression()])
        return node

    def parse_bool_term() -> Node:
        node = Parser.parse_rel_expression()
        while Parser.lexer.next.type == "AND":
            Parser.lexer.select_next()
            node = BinOp("and", [node, Parser.parse_rel_expression()])
        return node

    def parse_bool_expression() -> Node:
        node = Parser.parse_bool_term()
        while Parser.lexer.next.type == "OR":
            Parser.lexer.select_next()
            node = BinOp("or", [node, Parser.parse_bool_term()])
        return node

    def parse_block() -> Node:
        children = []
        while Parser.lexer.next.type == "END": Parser.lexer.select_next()
        while Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "UNTIL", "EOF"):
            stmt = Parser.parse_statement()
            if stmt:
                children.append(stmt)
            while Parser.lexer.next.type == "END": Parser.lexer.select_next()
        return Block(None, children)

    def parse_statement() -> Node:
        tok = Parser.lexer.next

        if tok.type == "END":
            Parser.lexer.select_next()
            return NoOp(None, [])

        elif tok.type == "VAR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception("[Parser] Expected identifier after 'local'")
            name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "TYPE":
                raise Exception("[Parser] Expected type after identifier in declaration")
            vartype = Parser.lexer.next.value
            Parser.lexer.select_next()
            ident = Identifier(name, [])
            node  = VarDec(vartype, [ident])
            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                node.children.append(Parser.parse_bool_expression())
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return node

        elif tok.type == "IF":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception("[Parser] Expected '(' after 'if'")
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception("[Parser] Expected ')' after if condition")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_IF_BRA":
                raise Exception("[Parser] Expected 'then' after if condition")
            Parser.lexer.select_next()
            then_block = Parser.parse_block()
            node = If(None, [cond, then_block])
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()
                else_block = Parser.parse_block()
                node.children.append(else_block)
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception("[Parser] Expected 'end' to close 'if'")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return node

        elif tok.type == "WHILE":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception("[Parser] Expected '(' after 'while'")
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception("[Parser] Expected ')' after while condition")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_BRA":
                raise Exception("[Parser] Expected 'do' after while condition")
            Parser.lexer.select_next()
            block = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception("[Parser] Expected 'end' to close 'while'")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return While(None, [cond, block])

        elif tok.type == "FOR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception("[Parser] Expected identifier after 'for'")
            var_name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception("[Parser] Expected '=' in 'for'")
            Parser.lexer.select_next()
            start = Parser.parse_expression()
            if Parser.lexer.next.type != "COMMA":
                raise Exception("[Parser] Expected ',' after start in 'for'")
            Parser.lexer.select_next()
            limit = Parser.parse_expression()
            for_children = [start, limit]
            if Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                for_children.append(Parser.parse_expression())
            if Parser.lexer.next.type != "OPEN_BRA":
                raise Exception("[Parser] Expected 'do' in 'for'")
            Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception("[Parser] Expected 'end' to close 'for'")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            for_children.append(body)
            return For(var_name, for_children)

        elif tok.type == "REPEAT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "UNTIL":
                raise Exception("[Parser] Expected 'until' to close 'repeat'")
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return Repeat(None, [body, cond])

        elif tok.type == "FUNCTION":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception("[Parser] Expected function name")
            fname = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception("[Parser] Expected '(' after function name")
            Parser.lexer.select_next()
            params = []
            if Parser.lexer.next.type != "CLOSE_PAR":
                if Parser.lexer.next.type != "IDEN":
                    raise Exception("[Parser] Expected parameter name")
                params.append(Parser.lexer.next.value)
                Parser.lexer.select_next()
                if Parser.lexer.next.type == "TYPE":
                    Parser.lexer.select_next()
                while Parser.lexer.next.type == "COMMA":
                    Parser.lexer.select_next()
                    if Parser.lexer.next.type != "IDEN":
                        raise Exception("[Parser] Expected parameter name")
                    params.append(Parser.lexer.next.value)
                    Parser.lexer.select_next()
                    if Parser.lexer.next.type == "TYPE":
                        Parser.lexer.select_next()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception("[Parser] Expected ')' in function definition")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "TYPE":
                Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception("[Parser] Expected 'end' to close function")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return FuncDef(fname, [body], params=params)

        elif tok.type == "RETURN":
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return ReturnNode(None, [expr])

        elif tok.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception("[Parser] Expected '(' after 'print'")
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception("[Parser] Expected ')' after print expression")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return Print(None, [expr])

        elif tok.type == "IDEN":
            name = tok.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in call to '{name}'")
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

        else:
            raise Exception(f"[Parser] Unexpected token '{tok.type}' ({tok.value!r}) in statement")

    def parse_program() -> Node:
        children = []
        while Parser.lexer.next.type == "END": Parser.lexer.select_next()
        while Parser.lexer.next.type != "EOF":
            stmt = Parser.parse_statement()
            if stmt:
                children.append(stmt)
            while Parser.lexer.next.type == "END": Parser.lexer.select_next()
        return Block(None, children)

    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()
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

    st  = SymbolTable()
    ast.generate(st)
    out = os.path.splitext(filename)[0] + ".asm"
    Code.dump(out)
    print(f"[OK] Assembly escrito em: {out}")


if __name__ == "__main__":
    main()