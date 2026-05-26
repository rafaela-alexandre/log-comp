import sys
import re
import os


class Token:
    def __init__(self, type: str, value):
        self.type = type
        self.value = value


class PrePro:
    def filter(code: str) -> str:
        return re.sub(r'--[^\n]*', '', code)


class Variable:
    def __init__(self, vartype: str, value=None, shift: int = 0, is_func: bool = False, is_struct: bool = False):
        self.vartype   = vartype
        self.value     = value
        self.shift     = shift
        self.is_func   = is_func
        self.is_struct = is_struct  # True se for declaração de struct (molde)


class SymbolTable:
    def __init__(self, parent=None):
        self.table  = {}
        self.offset = 0
        self.parent = parent

    def create_variable(self, name: str, vartype: str, is_func: bool = False, is_struct: bool = False):
        if name in self.table:
            raise Exception(f"[Semantic] Variable '{name}' already declared in this scope")
        self.offset += 4
        self.table[name] = Variable(vartype, None, self.offset, is_func, is_struct)

    def get_value(self, name: str):
        if name in self.table:
            return self.table[name]
        if self.parent is not None:
            return self.parent.get_value(name)
        raise Exception(f"[Semantic] Variable '{name}' not defined")

    def set_value(self, name: str, value, vartype: str = None):
        if name in self.table:
            var = self.table[name]
            if not var.is_func and not var.is_struct and vartype is not None and var.vartype != vartype:
                raise Exception(
                    f"[Semantic] Type mismatch for '{name}': expected {var.vartype}, got {vartype}"
                )
            var.value = value
            return
        if self.parent is not None:
            self.parent.set_value(name, value, vartype)
            return
        raise Exception(f"[Semantic] Variable '{name}' not defined")


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
        "struct":   "STRUCT",
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
        elif char == ".":
            if self.position + 1 < len(self.source) and self.source[self.position + 1] == ".":
                self.next = Token("CONCAT", "..")
                self.position += 2
            else:
                self.next = Token("DOT", ".")
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

    def evaluate(self, st):
        raise NotImplementedError("[Semantic] evaluate() not implemented")

    def generate(self, st):
        raise NotImplementedError("[CodeGen] generate() not implemented")


class IntVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("number", self.value)

    def generate(self, st):
        pass


class BoolVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("boolean", self.value)

    def generate(self, st):
        pass


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
        pass


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
        pass


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
            elif op == "<": res = left.value < right.value
            else:           res = left.value > right.value
            return Variable("boolean", res)
        if op == "..":
            def _tostr(v):
                if v.vartype == "boolean": return "true" if v.value else "false"
                return str(v.value)
            return Variable("string", _tostr(left) + _tostr(right))
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
        pass


class VarDec(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        name = self.children[0].value
        vartype = self.value

        # verifica se o tipo é uma struct declarada
        try:
            type_var = st.get_value(vartype)
            if type_var.is_struct:
                # instancia a struct: copia os campos do molde
                struct_dec = type_var.value
                fields = {}
                for field in struct_dec.children:
                    field_name = field.children[0].value
                    field_type = field.value
                    fields[field_name] = Variable(field_type, None)
                st.create_variable(name, vartype, is_func=False, is_struct=False)
                st.set_value(name, fields)
                return
        except Exception:
            pass  # tipo não é struct, continua normal

        st.create_variable(name, vartype, is_func=False)
        if len(self.children) > 1:
            result = self.children[1].evaluate(st)
            if result.vartype != vartype:
                raise Exception(
                    f"[Semantic] Type mismatch: cannot assign {result.vartype} to {vartype} variable '{name}'"
                )
            st.set_value(name, result.value, result.vartype)

    def generate(self, st):
        pass


class Assignment(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        result = self.children[1].evaluate(st)
        st.set_value(self.children[0].value, result.value, result.vartype)

    def generate(self, st):
        pass


class StructAccess(Node):
    """
    value      = field name
    children[0] = Identifier (instance name)
    """
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        instance_name = self.children[0].value
        field_name    = self.value
        var = st.get_value(instance_name)
        if not isinstance(var.value, dict):
            raise Exception(f"[Semantic] '{instance_name}' is not a struct instance")
        if field_name not in var.value:
            raise Exception(f"[Semantic] Struct '{instance_name}' has no field '{field_name}'")
        field = var.value[field_name]
        return Variable(field.vartype, field.value)

    def generate(self, st):
        pass


class StructFieldAssignment(Node):
    """
    value        = field name
    children[0]  = Identifier (instance name)
    children[1]  = expression
    """
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        instance_name = self.children[0].value
        field_name    = self.value
        result        = self.children[1].evaluate(st)
        var = st.get_value(instance_name)
        if not isinstance(var.value, dict):
            raise Exception(f"[Semantic] '{instance_name}' is not a struct instance")
        if field_name not in var.value:
            raise Exception(f"[Semantic] Struct '{instance_name}' has no field '{field_name}'")
        field = var.value[field_name]
        if field.vartype != result.vartype:
            raise Exception(
                f"[Semantic] Type mismatch for field '{field_name}': "
                f"expected {field.vartype}, got {result.vartype}"
            )
        field.value = result.value

    def generate(self, st):
        pass


class StructDec(Node):
    """
    value      = struct name
    children   = list of VarDec (fields)
    """
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        struct_name = self.value
        st.create_variable(struct_name, struct_name, is_func=False, is_struct=True)
        st.set_value(struct_name, self)

    def generate(self, st):
        pass


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
        pass


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
        pass


class NoOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return None

    def generate(self, st):
        pass


class Read(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return Variable("number", int(input()))

    def generate(self, st):
        pass


class If(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        cond = self.children[0].evaluate(st)
        if cond.vartype != "boolean":
            raise Exception("[Semantic] 'if' condition must be boolean")
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
        pass


class While(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        while True:
            cond = self.children[0].evaluate(st)
            if cond.vartype != "boolean":
                raise Exception("[Semantic] 'while' condition must be boolean")
            if not cond.value:
                break
            result = self.children[1].evaluate(st)
            if result is not None:
                return result
        return None

    def generate(self, st):
        pass


class Return(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return self.children[0].evaluate(st)

    def generate(self, st):
        pass


class FuncDec(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        func_name = self.children[0].value
        ret_type  = self.value if self.value else "void"
        st.create_variable(func_name, ret_type, is_func=True)
        st.set_value(func_name, self)

    def generate(self, st):
        pass


class FuncCall(Node):
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
            if param_type and val.vartype != param_type:
                raise Exception(
                    f"[Semantic] Argument type mismatch in call to '{func_name}': "
                    f"parameter '{param_name}' expects {param_type}, got {val.vartype}"
                )
            func_st.create_variable(param_name, param_type or val.vartype)
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
        pass


_parser_func_depth = 0


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
                Parser.lexer.select_next()
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in function call")
                Parser.lexer.select_next()
                return FuncCall(name, args)
            elif Parser.lexer.next.type == "DOT":
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "IDEN":
                    raise Exception(f"[Parser] Expected field name after '.'")
                field_name = Parser.lexer.next.value
                Parser.lexer.select_next()
                return StructAccess(field_name, [Identifier(name, [])])
            return Identifier(name, [])
        else:
            raise Exception(f"[Parser] Unexpected token '{tok.type}', expected factor")

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
        if Parser.lexer.next.type == "CONCAT":
            Parser.lexer.select_next()
            right = Parser.parse_rel_expression()
            return BinOp("..", [node, right])
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
        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
        while Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "EOF"):
            stmt = Parser.parse_statement()
            if stmt:
                children.append(stmt)
            while Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
        return Block(None, children)

    def parse_var_declaration() -> Node:
        Parser.lexer.select_next()  # consume 'local'
        if Parser.lexer.next.type != "IDEN":
            raise Exception("[Parser] Expected identifier after 'local'")
        name = Parser.lexer.next.value
        Parser.lexer.select_next()
        # tipo pode ser TYPE ou IDEN (nome de struct)
        if Parser.lexer.next.type not in ("TYPE", "IDEN"):
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

    def parse_struct_declaration() -> Node:
        Parser.lexer.select_next()  # consume 'struct'
        if Parser.lexer.next.type != "IDEN":
            raise Exception("[Parser] Expected struct name after 'struct'")
        struct_name = Parser.lexer.next.value
        Parser.lexer.select_next()
        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
        fields = []
        while Parser.lexer.next.type not in ("CLOSE_BRA", "EOF"):
            if Parser.lexer.next.type == "VAR":
                Parser.lexer.select_next()  # consume 'local'
                if Parser.lexer.next.type != "IDEN":
                    raise Exception("[Parser] Expected field name")
                field_name = Parser.lexer.next.value
                Parser.lexer.select_next()
                if Parser.lexer.next.type not in ("TYPE", "IDEN"):
                    raise Exception("[Parser] Expected field type")
                field_type = Parser.lexer.next.value
                Parser.lexer.select_next()
                fields.append(VarDec(field_type, [Identifier(field_name, [])]))
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
            elif Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            else:
                raise Exception(f"[Parser] Unexpected token in struct: {Parser.lexer.next.type}")
        if Parser.lexer.next.type != "CLOSE_BRA":
            raise Exception("[Parser] Expected 'end' to close struct")
        Parser.lexer.select_next()
        if Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
        return StructDec(struct_name, fields)

    def parse_func_declaration() -> Node:
        global _parser_func_depth
        if _parser_func_depth > 0:
            raise Exception("[Parser] Cannot define a function inside another function")
        Parser.lexer.select_next()
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
        _parser_func_depth += 1
        body = Parser.parse_block()
        _parser_func_depth -= 1
        if Parser.lexer.next.type != "CLOSE_BRA":
            raise Exception("[Parser] Expected 'end' to close function")
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
            if Parser.lexer.next.type == "DOT":
                # x.b = expr
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "IDEN":
                    raise Exception("[Parser] Expected field name after '.'")
                field_name = Parser.lexer.next.value
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "ASSIGN":
                    raise Exception("[Parser] Expected '=' after field access")
                Parser.lexer.select_next()
                expr = Parser.parse_bool_expression()
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
                return StructFieldAssignment(field_name, [Identifier(name, []), expr])
            elif Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                expr = Parser.parse_bool_expression()
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
                return Assignment(None, [Identifier(name, []), expr])
            elif Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' in function call")
                Parser.lexer.select_next()
                if Parser.lexer.next.type == "END":
                    Parser.lexer.select_next()
                return FuncCall(name, args)
            else:
                raise Exception(f"[Parser] Expected '=', '(' or '.' after '{name}'")

        elif tok.type == "FUNC":
            return Parser.parse_func_declaration()

        elif tok.type == "STRUCT":
            return Parser.parse_struct_declaration()

        else:
            raise Exception(f"[Parser] Unexpected token '{tok.type}' in statement")

    def parse_program() -> Node:
        children = []
        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
        while Parser.lexer.next.type != "EOF":
            if Parser.lexer.next.type == "FUNC":
                node = Parser.parse_func_declaration()
            elif Parser.lexer.next.type == "STRUCT":
                node = Parser.parse_struct_declaration()
            else:
                node = Parser.parse_statement()
            if node:
                children.append(node)
            while Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
        return Block(None, children)

    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()
        node = Parser.parse_program()
        if Parser.lexer.next.type != "EOF":
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected EOF")
        return node


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