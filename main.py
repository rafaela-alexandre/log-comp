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

    RESERVED = {"print"}

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
            self.next = Token("ASSIGN", "=")
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
            if iden in Lexer.RESERVED:
                self.next = Token(iden.upper(), iden)
            else:
                self.next = Token("IDEN", iden)
        else:
            raise Exception(f"[Lexer] Invalid symbol '{char}'")


class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children if children is not None else []

    def evaluate(self, st):
        raise NotImplementedError("[Semantic] evaluate() not implemented")


class IntVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return self.value


class UnOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        if self.value == "+":
            return +self.children[0].evaluate(st)
        elif self.value == "-":
            return -self.children[0].evaluate(st)
        else:
            raise Exception(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

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
        else:
            raise Exception(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        return st.get_value(self.value)


class Assignment(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        st.set_value(self.children[0].value, self.children[1].evaluate(st))


class Print(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        print(self.children[0].evaluate(st))


class Block(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        for child in self.children:
            child.evaluate(st)


class NoOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self, st):
        pass


class Parser:
    lexer = None  # atributo estático

    def parse_factor() -> Node:
        if Parser.lexer.next.type == "PLUS":
            Parser.lexer.select_next()
            return UnOp("+", [Parser.parse_factor()])

        elif Parser.lexer.next.type == "MINUS":
            Parser.lexer.select_next()
            return UnOp("-", [Parser.parse_factor()])

        elif Parser.lexer.next.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_expression()
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

    def parse_statement() -> Node:
        # linha vazia
        if Parser.lexer.next.type == "END":
            Parser.lexer.select_next()
            return NoOp(None, [])

        # atribuição: IDEN = EXPRESSION
        elif Parser.lexer.next.type == "IDEN":
            iden = Identifier(Parser.lexer.next.value, [])
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "ASSIGN":
                raise Exception(f"[Parser] Expected '=' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_expression()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return Assignment(None, [iden, expr])

        # print(EXPRESSION)
        elif Parser.lexer.next.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise Exception(f"[Parser] Expected '(' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            expr = Parser.parse_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "END":
                raise Exception(f"[Parser] Expected newline but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return Print(None, [expr])

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