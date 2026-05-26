import sys
import re


class Token:
    def __init__(self, type: str, value):
        self.type = type
        self.value = value


class PrePro:
    def filter(code: str) -> str:
        return re.sub(r'--[^\n]*', '', code)


class Variable:
    def __init__(self, value, vartype: str):
        self.value = value
        self.vartype = vartype


class SymbolTable:
    def __init__(self):
        self.table = {}

    def create_variable(self, name: str, vartype: str):
        if name in self.table:
            raise Exception(f"[Semantic] Variable '{name}' already declared")
        self.table[name] = Variable(None, vartype)

    def get_value(self, name: str):
        if name not in self.table:
            raise Exception(f"[Semantic] Variable '{name}' not defined")
        return self.table[name].value, self.table[name].vartype

    def set_value(self, name: str, value, vartype: str):
        if name not in self.table:
            raise Exception(f"[Semantic] Variable '{name}' not declared")
        if self.table[name].vartype != vartype:
            raise Exception(f"[Semantic] Type mismatch for '{name}': expected {self.table[name].vartype}, got {vartype}")
        self.table[name].value = value


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = None

    RESERVED = {
        "print": "PRINT",
        "if": "IF",
        "else": "ELSE",
        "while": "WHILE",
        "and": "AND",
        "or": "OR",
        "not": "NOT",
        "read": "READ",
        "then": "OPEN_IF_BRA",
        "do": "OPEN_BRA",
        "end": "CLOSE_BRA",
        "local": "VAR",
        "true": "BOOL",
        "false": "BOOL",
        "number": "TYPE",
        "string": "TYPE",
        "boolean": "TYPE",
        "float": "TYPE",
    }

    def select_next(self):
        while self.position < len(self.source) and self.source[self.position] == " ":
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
                raise Exception(f"[Lexer] Invalid symbol '.'")
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
            if self.position < len(self.source) and self.source[self.position] == ".":
                num += "."
                self.position += 1
                while self.position < len(self.source) and self.source[self.position].isdigit():
                    num += self.source[self.position]
                    self.position += 1
                self.next = Token("FLOAT", float(num))
            else:
                self.next = Token("INT", int(num))
        elif char.isalpha() or char == "_":
            iden = ""
            while self.position < len(self.source) and (self.source[self.position].isalnum() or self.source[self.position] == "_"):
                iden += self.source[self.position]
                self.position += 1
            token_type = Lexer.RESERVED.get(iden, "IDEN")
            if token_type == "BOOL":
                self.next = Token("BOOL", iden == "true")
            else:
                self.next = Token(token_type, iden)
        else:
            raise Exception(f"[Lexer] Invalid symbol '{char}'")


class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children if children is not None else []

    def evaluate(self, st):
        raise NotImplementedError("[Semantic] evaluate() not implemented")


class IntVal(Node):
    def evaluate(self, st):
        return self.value, "number"


class FloatVal(Node):
    def evaluate(self, st):
        return self.value, "float"


class BoolVal(Node):
    def evaluate(self, st):
        return self.value, "boolean"


class StringVal(Node):
    def evaluate(self, st):
        return self.value, "string"

class CastOp(Node):
    def evaluate(self, st):
        val, vartype = self.children[0].evaluate(st)
        target = self.value
        if target == "number":
            if vartype == "number":
                return val, "number"
            elif vartype == "float":
                return round(val), "number"  # round, não int
            else:
                raise Exception(f"[Semantic] Cannot cast {vartype} to number")
        elif target == "float":
            if vartype == "float":
                return val, "float"          # mantém float
            elif vartype == "number":
                return float(val), "float"
            else:
                raise Exception(f"[Semantic] Cannot cast {vartype} to float")
        elif target == "string":
            return str(val), "string"
        elif target == "boolean":
            raise Exception(f"[Semantic] Cannot cast to boolean")
        else:
            raise Exception(f"[Semantic] Unknown cast target '{target}'")


class UnOp(Node):
    def evaluate(self, st):
        val, vartype = self.children[0].evaluate(st)
        if self.value == "+":
            if vartype not in ("number", "float"):
                raise Exception("[Semantic] Unary '+' requires number or float")
            return +val, vartype
        elif self.value == "-":
            if vartype not in ("number", "float"):
                raise Exception("[Semantic] Unary '-' requires number or float")
            return -val, vartype
        elif self.value == "not":
            if vartype != "boolean":
                raise Exception("[Semantic] 'not' requires boolean")
            return not val, "boolean"
        else:
            raise Exception(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def evaluate(self, st):
        left, ltype = self.children[0].evaluate(st)
        right, rtype = self.children[1].evaluate(st)
        op = self.value

        if op == "..":
            def to_str(v, t):
                if t == "boolean":
                    return "true" if v else "false"
                return str(v)
            return to_str(left, ltype) + to_str(right, rtype), "string"
        elif op == "and":
            if ltype != "boolean" or rtype != "boolean":
                raise Exception("[Semantic] 'and' requires booleans")
            return left and right, "boolean"
        elif op == "or":
            if ltype != "boolean" or rtype != "boolean":
                raise Exception("[Semantic] 'or' requires booleans")
            return left or right, "boolean"
        elif op in ("==", "<", ">"):
            if ltype != rtype:
                raise Exception(f"[Semantic] Type mismatch in '{op}'")
            if op == "==":
                return left == right, "boolean"
            elif op == "<":
                return left < right, "boolean"
            else:
                return left > right, "boolean"
        elif op in ("+", "-", "*", "/"):
            numeric = {"number", "float"}
            if ltype not in numeric or rtype not in numeric:
                if op == "+" and ltype == "string" and rtype == "string":
                    return left + right, "string"
                raise Exception(f"[Semantic] '{op}' cannot operate on {ltype} and {rtype}")
            # float wins
            result_type = "float" if "float" in (ltype, rtype) else "number"
            if op == "+":
                result = left + right
            elif op == "-":
                result = left - right
            elif op == "*":
                result = left * right
            else:
                if right == 0:
                    raise Exception("[Semantic] Division by zero")
                result = left / right if result_type == "float" else left // right
            return result, result_type
        else:
            raise Exception(f"[Semantic] Unknown binary operator '{op}'")


class Identifier(Node):
    def evaluate(self, st):
        return st.get_value(self.value)


class Assignment(Node):
    def evaluate(self, st):
        val, vartype = self.children[1].evaluate(st)
        st.set_value(self.children[0].value, val, vartype)


class VarDec(Node):
    def evaluate(self, st):
        name = self.children[0].value
        st.create_variable(name, self.value)
        if len(self.children) > 1:
            val, vartype = self.children[1].evaluate(st)
            if vartype != self.value:
                raise Exception(f"[Semantic] Type mismatch in declaration of '{name}': expected {self.value}, got {vartype}")
            st.set_value(name, val, vartype)


class Print(Node):
    def evaluate(self, st):
        val, vartype = self.children[0].evaluate(st)
        if vartype == "boolean":
            print("true" if val else "false")
        else:
            print(val)


class Block(Node):
    def evaluate(self, st):
        for child in self.children:
            child.evaluate(st)


class NoOp(Node):
    def evaluate(self, st):
        pass


class Read(Node):
    def evaluate(self, st):
        return int(input()), "number"


class If(Node):
    def evaluate(self, st):
        val, vartype = self.children[0].evaluate(st)
        if vartype != "boolean":
            raise Exception("[Semantic] 'if' condition must be boolean")
        if val:
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)


class While(Node):
    def evaluate(self, st):
        while True:
            val, vartype = self.children[0].evaluate(st)
            if vartype != "boolean":
                raise Exception("[Semantic] 'while' condition must be boolean")
            if not val:
                break
            self.children[1].evaluate(st)


class Parser:
    lexer = None

    def parse_factor() -> Node:
        if Parser.lexer.next.type == "PLUS":
            Parser.lexer.select_next()
            return UnOp("+", [Parser.parse_factor()])
        elif Parser.lexer.next.type == "MINUS":
            Parser.lexer.select_next()
            return UnOp("-", [Parser.parse_factor()])
        elif Parser.lexer.next.type == "NOT":
            Parser.lexer.select_next()
            return UnOp("not", [Parser.parse_factor()])
        elif Parser.lexer.next.type == "OPEN_PAR":
            # lookahead: se o próximo for TYPE, é um cast
            saved_pos = Parser.lexer.position
            saved_next = Parser.lexer.next
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "TYPE":
                target_type = Parser.lexer.next.value
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' after cast type but got {Parser.lexer.next.type}")
                Parser.lexer.select_next()
                return CastOp(target_type, [Parser.parse_factor()])
            else:
                node = Parser.parse_bool_expression()
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
                Parser.lexer.select_next()
                return node
        elif Parser.lexer.next.type == "INT":
            node = IntVal(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            return node
        elif Parser.lexer.next.type == "FLOAT":
            node = FloatVal(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            return node
        elif Parser.lexer.next.type == "BOOL":
            node = BoolVal(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            return node
        elif Parser.lexer.next.type == "STR":
            node = StringVal(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            return node
        elif Parser.lexer.next.type == "IDEN":
            node = Identifier(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            return node
        elif Parser.lexer.next.type == "READ":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' after read but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' after read( but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return Read(None, [])
        else:
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected factor")

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
        while Parser.lexer.next.type == "CONCAT":
            Parser.lexer.select_next()
            node = BinOp("..", [node, Parser.parse_expression()])
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
            children.append(Parser.parse_statement())
            while Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
        return Block(None, children)

    def parse_statement() -> Node:
        if Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
            return NoOp(None, [])

        elif Parser.lexer.next.type == "VAR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception(f"[Parser] Expected identifier after 'local' but got {Parser.lexer.next.type}")
            iden = Identifier(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "TYPE":
                raise Exception(f"[Parser] Expected type after identifier but got {Parser.lexer.next.type}")
            vartype = Parser.lexer.next.value
            Parser.lexer.select_next()
            node = VarDec(vartype, [iden])
            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                node.children.append(Parser.parse_bool_expression())
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return node

        elif Parser.lexer.next.type == "IF":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' after 'if' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' after if condition but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_IF_BRA":
                raise Exception(f"[Parser] Expected 'then' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            then_block = Parser.parse_block()
            node = If(None, [cond, then_block])
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()
                else_block = Parser.parse_block()
                node.children.append(else_block)
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception(f"[Parser] Expected 'end' to close 'if' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return node

        elif Parser.lexer.next.type == "WHILE":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' after 'while' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' after while condition but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_BRA":
                raise Exception(f"[Parser] Expected 'do' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            block = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception(f"[Parser] Expected 'end' to close 'while' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return While(None, [cond, block])

        elif Parser.lexer.next.type == "IDEN":
            iden = Identifier(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception(f"[Parser] Expected '=' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return Assignment(None, [iden, expr])

        elif Parser.lexer.next.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return Print(None, [expr])

        elif Parser.lexer.next.type == "OPEN_BRA":
            Parser.lexer.select_next()
            block = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception(f"[Parser] Expected 'end' to close 'do' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return block

        else:
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type} in statement")

    def parse_program() -> Node:
        children = []
        while Parser.lexer.next.type != "EOF":
            children.append(Parser.parse_statement())
        return Block(None, children)

    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()
        node = Parser.parse_program()
        if Parser.lexer.next.type != "EOF":
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected EOF")
        return node


def main():
    filename = sys.argv[1]
    with open(filename, "r") as f:
        code = f.read() + "\n"
    code = PrePro.filter(code)
    st = SymbolTable()
    Parser.run(code).evaluate(st)


if __name__ == "__main__":
    main()