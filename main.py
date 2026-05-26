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
        elif self.v