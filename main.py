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
    def __init__(self, value):
        self.value = value


class SymbolTable:
    def __init__(self):
        self.table = {}

    def get_value(self, name: str):
        if name not in self.table:
            raise Exception(f"[Semantic] Variable '{name}' not defined")
        return self.table[name].value

    def set_value(self, name: str, value):
        self.table[name] = Variable(value)


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
        "for": "FOR",
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
        elif char.isdigit():
            num = ""
            while self.position < len(self.source) and self.source[self.position].isdigit():
                num += self.source[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
        elif char.isalpha():
            iden = ""
            while self.position < len(self.source) and (self.source[self.position].isalnum() or self.source[self.position] == "_"):
                iden += self.source[self.position]
                self.position += 1
            token_type = Lexer.RESERVED.get(iden, "IDEN")
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
        return self.value


class UnOp(Node):
    def evaluate(self, st):
        if self.value == "+":
            return +self.children[0].evaluate(st)
        elif self.value == "-":
            return -self.children[0].evaluate(st)
        elif self.value == "not":
            return not self.children[0].evaluate(st)
        else:
            raise Exception(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def evaluate(self, st):
        left = self.children[0].evaluate(st)
        right = self.children[1].evaluate(st)
        if self.value == "+":
            return left + right
        elif self.value == "-":
            return left - right
        elif self.value == "*":
            return left * right
        elif self.value == "/":
            if right == 0:
                raise Exception("[Semantic] Division by zero")
            return left // right
        elif self.value == "==":
            return left == right
        elif self.value == "<":
            return left < right
        elif self.value == ">":
            return left > right
        elif self.value == "and":
            return left and right
        elif self.value == "or":
            return left or right
        else:
            raise Exception(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    def evaluate(self, st):
        return st.get_value(self.value)


class Assignment(Node):
    def evaluate(self, st):
        st.set_value(self.children[0].value, self.children[1].evaluate(st))


class Print(Node):
    def evaluate(self, st):
        print(self.children[0].evaluate(st))


class Block(Node):
    def evaluate(self, st):
        for child in self.children:
            child.evaluate(st)


class NoOp(Node):
    def evaluate(self, st):
        pass


class Read(Node):
    def evaluate(self, st):
        return int(input())


class If(Node):
    def evaluate(self, st):
        if self.children[0].evaluate(st):
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)


class IfExpr(Node):
    # children: [cond, then_expr, else_expr]
    def evaluate(self, st):
        if self.children[0].evaluate(st):
            return self.children[1].evaluate(st)
        else:
            return self.children[2].evaluate(st)


class While(Node):
    def evaluate(self, st):
        while self.children[0].evaluate(st):
            self.children[1].evaluate(st)


class For(Node):
    # value = loop variable name
    # children: [start_expr, end_expr, block]
    def evaluate(self, st):
        start = self.children[0].evaluate(st)
        end = self.children[1].evaluate(st)
        for i in range(start, end + 1):
            st.set_value(self.value, i)
            self.children[2].evaluate(st)


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
        elif Parser.lexer.next.type == "IF":
            # if expression: if BOOLEXPR then BOOLEXPR else BOOLEXPR end
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "OPEN_IF_BRA":
                raise Exception(f"[Parser] Expected 'then' in if expression but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            then_expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "ELSE":
                raise Exception(f"[Parser] Expected 'else' in if expression but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            else_expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception(f"[Parser] Expected 'end' to close if expression but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return IfExpr(None, [cond, then_expr, else_expr])
        elif Parser.lexer.next.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return node
        elif Parser.lexer.next.type == "INT":
            node = IntVal(Parser.lexer.next.value, [])
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

        elif Parser.lexer.next.type == "FOR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise Exception(f"[Parser] Expected identifier after 'for' but got {Parser.lexer.next.type}")
            var_name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception(f"[Parser] Expected '=' after for variable but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            start = Parser.parse_expression()
            if Parser.lexer.next.type != "COMMA":
                raise Exception(f"[Parser] Expected ',' after for start but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            end = Parser.parse_expression()
            if Parser.lexer.next.type != "OPEN_BRA":
                raise Exception(f"[Parser] Expected 'do' after for range but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            block = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise Exception(f"[Parser] Expected 'end' to close 'for' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
            return For(var_name, [start, end, block])

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