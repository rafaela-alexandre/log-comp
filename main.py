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
        # Pula espaços em branco
        while self.position < len(self.source) and self.source[self.position] == " ":
            self.position += 1

        # Fim da entrada
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

        elif char.isdigit():
            num = ""
            while self.position < len(self.source) and self.source[self.position].isdigit():
                num += self.source[self.position]
                self.position += 1
            self.next = Token("INT", int(num))

        else:
            raise Exception(f"[Lexer] Invalid symbol '{char}'")


class Parser:
    lexer: Lexer = None

    def parse_expression() -> int:
        if Parser.lexer.next.type != "INT":
            raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected INT")

        result = Parser.lexer.next.value
        Parser.lexer.select_next()

        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()

            if Parser.lexer.next.type != "INT":
                raise Exception(f"[Parser] Unexpected token {Parser.lexer.next.type}, expected INT")

            if op == "PLUS":
                result += Parser.lexer.next.value
            else:
                result -= Parser.lexer.next.value

            Parser.lexer.select_next()

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