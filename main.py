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


class Parser:
    lexer = None  # atributo estático

    def parse_factor() -> int:
        if Parser.lexer.next.type == "PLUS":
            Parser.lexer.select_next()
            return +Parser.parse_factor()

        elif Parser.lexer.next.type == "MINUS":
            Parser.lexer.select_next()
            return -Parser.parse_factor()

        elif Parser.lexer.next.type == "OPEN_PAR":
            Parser.lexer.select_next()
            result = Parser.parse_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise Exception(f"[Parser] Expected ')' but got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return result

        elif Parser.lexer.next.type == "INT":
            result = Parser.lexer.next.value
            Parser.lexer.select_next()
            return result

        else:
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected factor")

    def parse_term() -> int:
        result = Parser.parse_factor()

        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()
            if op == "MULT":
                result *= Parser.parse_factor()
            else:
                result //= Parser.parse_factor()

        return result

    def parse_expression() -> int:
        result = Parser.parse_term()

        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()
            if op == "PLUS":
                result += Parser.parse_term()
            else:
                result -= Parser.parse_term()

        return result

    def run(code: str) -> int:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        result = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected EOF")

        return result


def main():
    code = sys.argv[1]
    result = Parser.run(code)
    print(result)


if __name__ == "__main__":
    main()