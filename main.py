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
    def __init__(self, vartype: str, value=None, shift: int = 0, is_func: bool = False):
        self.vartype = vartype
        self.value   = value
        self.shift   = shift
        self.is_func = is_func


class SymbolTable:
    def __init__(self, parent=None):
        self.table  = {}
        self.offset = 0
        self.parent = parent

    def create_variable(self, name: str, vartype: str, is_func: bool = False):
        if name in self.table:
            raise Exception(f"[Semantic] Variable '{name}' already declared in this scope")
        self.offset += 4
        self.table[name] = Variable(vartype, None, self.offset, is_func)

    def get_value(self, name: str):
        if name in self.table:
            return self.table[name]
        if self.parent is not None:
            return self.parent.get_value(name)
        raise Exception(f"[Semantic] Variable '{name}' not defined")

    def set_value(self, name: str, value, vartype: str = None):
        if name in self.table:
            var = self.table[name]
            if vartype is not None and var.vartype != vartype:
                raise Exception(
                    f"[Semantic] Type mismatch for '{name}': expected {var.vartype}, got {vartype}"
                )
            var.value = value
            return
        if self.parent is not None:
            self.parent.set_value(name, value, vartype)
            return
        raise Exception(f"[Semantic] Variable '{name}' not defined")


# ─────────────────────────────────────────────
#  CODE
# ─────────────────────────────────────────────

class Code:
    instructions = []

    def append(code: str) -> None:
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
        "function": "FUNC",
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
        pass


class Identifier(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return st.get_value(self.value)

    def generate(self, st):
        var = st.get_value(self.value)
        Code.append(f"  mov eax, [ebp-{var.shift}] ; {self.value}")


class UnOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        child = self.children[0].evaluate(st)
        if self.value == "+":
            if child.vartype != "number":
                raise Exception("[Semantic] Unary '+' requires number")
            return Variable("number", +child.value)
        elif self.value == "-":
            if child.vartype != "number":
                raise Exception("[Semantic] Unary '-' requires number")
            return Variable("number", -child.value)
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
            Code.append("  cmp eax, 0")
            Code.append("  mov eax, 0")
            Code.append("  mov ecx, 1")
            Code.append("  cmove eax, ecx ; not")


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
        if op in ("==", "<", ">"):
            if left.vartype != right.vartype:
                raise Exception(f"[Semantic] Type mismatch in '{op}'")
            if op == "==": res = left.value == right.value
            elif op == "<": res = left.value <  right.value
            else:           res = left.value >  right.value
            return Variable("boolean", res)
        if left.vartype == "string" or right.vartype == "string":
            if op == "+":
                return Variable("string", str(left.value) + str(right.value))
            raise Exception(f"[Semantic] Operator '{op}' not valid for strings")
        if left.vartype != "number" or right.vartype != "number":
            raise Exception(f"[Semantic] Operator '{op}' requires numbers")
        if op == "+": return Variable("number", left.value + right.value)
        if op == "-": return Variable("number", left.value - right.value)
        if op == "*": return Variable("number", left.value * right.value)
        if op == "/":
            if right.value == 0:
                raise Exception("[Semantic] Division by zero")
            return Variable("number", left.value // right.value)
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
        st.create_variable(name, self.value, is_func=False)
        if len(self.children) > 1:
            result = self.children[1].evaluate(st)
            st.set_value(name, result.value, result.vartype)

    def generate(self, st):
        name = self.children[0].value
        st.create_variable(name, self.value, is_func=False)
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
        var = st.get_value(self.children[0].value)
        Code.append(f"  mov [ebp-{var.shift}], eax ; {self.children[0].value} = ...")


class Print(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        result = self.children[0].evaluate(st)
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
            result = self.children[1].evaluate(st)
            if result is not None:
                return result
        elif len(self.children) > 2:
            result = self.children[2].evaluate(st)
            if result is not None:
                return result
        return None

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
            result = self.children[1].evaluate(st)
            if result is not None:
                return result
        return None

    def generate(self, st):
        uid = self.uid
        Code.append(f"  loop_{uid}: ; label do loop")
        self.children[0].generate(st)
        Code.append(f"  cmp eax, 0 ; se a condicao for falsa, sai")
        Code.append(f"  je exit_{uid}")
        self.children[1].generate(st)
        Code.append(f"  jmp loop_{uid}")
        Code.append(f"  exit_{uid}:")


class Block(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        for child in self.children:
            if isinstance(child, Block):
                inner_st = SymbolTable(parent=st)
                result = child.evaluate(inner_st)
            else:
                result = child.evaluate(st)
            if result is not None:
                return result
        return None

    def generate(self, st):
        for child in self.children:
            child.generate(st)


class NoOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return None

    def generate(self, st):
        pass


class Return(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return self.children[0].evaluate(st)

    def generate(self, st):
        raise NotImplementedError("[CodeGen] Return.generate() not implemented")


class FuncDec(Node):
    """
    value      = tipo de retorno (str ou None para void)
    children[0]    = Identifier (nome)
    children[1..n] = VarDec (parametros)
    children[-1]   = Block (corpo)
    """
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        func_name = self.children[0].value
        ret_type  = self.value if self.value else "void"
        st.create_variable(func_name, ret_type, is_func=True)
        st.set_value(func_name, self)

    def generate(self, st):
        raise NotImplementedError("[CodeGen] FuncDec.generate() not implemented")


class FuncCall(Node):
    """
    value    = nome da função (str)
    children = expressões dos argumentos
    """
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        func_name = self.value

        try:
            var = st.get_value(func_name)
        except Exception:
            raise Exception(f"[Semantic] Function '{func_name}' not defined")

        if not var.is_func:
            raise Exception(f"[Semantic] '{func_name}' is not a function")

        func_dec = var.value
        if not isinstance(func_dec, FuncDec):
            raise Exception(f"[Semantic] '{func_name}' has no valid declaration")

        param_nodes  = func_dec.children[1:-1]
        arg_nodes    = self.children

        if len(arg_nodes) != len(param_nodes):
            raise Exception(
                f"[Semantic] Function '{func_name}' expects {len(param_nodes)} argument(s), "
                f"got {len(arg_nodes)}"
            )

        evaluated_args = [arg.evaluate(st) for arg in arg_nodes]

        func_st = SymbolTable(parent=st)

        for param, val in zip(param_nodes, evaluated_args):
            param_name = param.children[0].value
            param_type = param.value
            if val.vartype != param_type:
                raise Exception(
                    f"[Semantic] Argument type mismatch in call to '{func_name}': "
                    f"parameter '{param_name}' expects {param_type}, got {val.vartype}"
                )
            func_st.create_variable(param_name, param_type)
            func_st.set_value(param_name, val.value)

        body   = func_dec.children[-1]
        result = body.evaluate(func_st)

        ret_type = func_dec.value
        if ret_type and ret_type != "void":
            if result is None:
                raise Exception(f"[Semantic] Function '{func_name}' must return a value of type {ret_type}")
            if result.vartype != ret_type:
                raise Exception(
                    f"[Semantic] Function '{func_name}' must return {ret_type}, got {result.vartype}"
                )
            return result
        return None

    def generate(self, st):
        raise NotImplementedError("[CodeGen] FuncCall.generate() not implemented")


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
                Parser.lexer.select_next()  # consume '('
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in function call, got {Parser.lexer.next.type}")
                Parser.lexer.select_next()  # consume ')'
                return FuncCall(name, args)
            return Identifier(name, [])
        else:
            raise Exception(f"[Parser] Unexpected token '{tok.type}' ({tok.value!r}), expected factor")

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

    def parse_rel_expression() -> Node:
        node = Parser.parse_expression()
        if Parser.lexer.next.type in ("EQ", "LT", "GT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = BinOp(op, [node, Parser.parse_expression()])
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
        while Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "EOF"):
            stmt = Parser.parse_statement()
            if stmt:
                children.append(stmt)
            while Parser.lexer.next.type == "END": Parser.lexer.select_next()
        return Block(None, children)

    def parse_var_declaration() -> Node:
        Parser.lexer.select_next()  # consume 'local'
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

    def parse_func_declaration() -> Node:
        Parser.lexer.select_next()  # consume 'function'

        if Parser.lexer.next.type != "IDEN":
            raise Exception("[Parser] Expected function name after 'function'")
        func_name = Parser.lexer.next.value
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "OPEN_PAR":
            raise Exception("[Parser] Expected '(' after function name")
        Parser.lexer.select_next()

        params = []
        if Parser.lexer.next.type == "IDEN":
            param_name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "TYPE":
                raise Exception("[Parser] Expected type after parameter name")
            param_type = Parser.lexer.next.value
            Parser.lexer.select_next()
            params.append(VarDec(param_type, [Identifier(param_name, [])]))
            while Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "IDEN":
                    raise Exception("[Parser] Expected parameter name after ','")
                param_name = Parser.lexer.next.value
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "TYPE":
                    raise Exception("[Parser] Expected type after parameter name")
                param_type = Parser.lexer.next.value
                Parser.lexer.select_next()
                params.append(VarDec(param_type, [Identifier(param_name, [])]))

        if Parser.lexer.next.type != "CLOSE_PAR":
            raise Exception("[Parser] Expected ')' after function parameters")
        Parser.lexer.select_next()

        ret_type = None
        if Parser.lexer.next.type == "TYPE":
            ret_type = Parser.lexer.next.value
            Parser.lexer.select_next()

        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()

        body = Parser.parse_block()

        if Parser.lexer.next.type != "CLOSE_BRA":
            raise Exception("[Parser] Expected 'end' to close function declaration")
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

        elif tok.type == "RETURN":
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return Return(None, [expr])

        elif tok.type == "VAR":
            return Parser.parse_var_declaration()

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

        elif tok.type == "OPEN_BRA":
            Parser.lexer.select_next()
            block = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception("[Parser] Expected 'end' to close 'do'")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return block

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
            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                expr = Parser.parse_bool_expression()
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
                return Assignment(None, [Identifier(name, []), expr])
            elif Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()  # consume '('
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in function call, got {Parser.lexer.next.type}")
                Parser.lexer.select_next()  # consume ')'
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
                return FuncCall(name, args)
            else:
                raise Exception(
                    f"[Parser] Expected '=' or '(' after identifier '{name}', "
                    f"got {Parser.lexer.next.type}"
                )

        else:
            raise Exception(f"[Parser] Unexpected token '{tok.type}' ({tok.value!r}) in statement")

    def parse_program() -> Node:
        children = []
        while Parser.lexer.next.type == "END": Parser.lexer.select_next()
        while Parser.lexer.next.type != "EOF":
            if Parser.lexer.next.type == "FUNC":
                node = Parser.parse_func_declaration()
            else:
                node = Parser.parse_statement()
            if node:
                children.append(node)
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

    st = SymbolTable()
    ast.evaluate(st)


if __name__ == "__main__":
    main()