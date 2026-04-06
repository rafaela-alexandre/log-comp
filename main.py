import sys


class Token:
    def __init__(self, type: str, value):
        self.type = type
        self.value = value


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = None

    def select_next(self):
        while self.position < len(self.source) and self.source[self.position] == " ":
            self.position += 1

        if self.position >= len(self.source):
            self.next = Token("EOF", "")
            return

        char = self.source[self.position]

        if char == "+":
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
        elif char.isdigit():
            num = ""
            while self.position < len(self.source) and self.source[self.position].isdigit():
                num += self.source[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
        else:
            raise Exception(f"[Lexer] Invalid symbol '{char}'")


class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children if children is not None else []

    def evaluate(self):
        raise NotImplementedError("[Semantic] evaluate() not implemented")


class IntVal(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self):
        return self.value


class UnOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self):
        if self.value == "+":
            return +self.children[0].evaluate()
        elif self.value == "-":
            return -self.children[0].evaluate()
        else:
            raise Exception(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def __init__(self, value, children):
        super().__init__(value, children)

    def evaluate(self):
        left = self.children[0].evaluate()
        right = self.children[1].evaluate()
        if self.value == "+":
            return left + right
        elif self.value == "-":
            return left - right
        elif self.value == "*":
            return left * right
        elif self.value == "/":
            return left // right
        else:
            raise Exception(f"[Semantic] Unknown binary operator '{self.value}'")


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

    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        node = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected EOF")

        return node


def main():
    code = sys.argv[1]
    result = Parser.run(code).evaluate()
    print(result)


if __name__ == "__main__":
    main()