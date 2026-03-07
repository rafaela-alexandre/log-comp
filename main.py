import sys


def main():
    entrada = sys.argv[1]

    resultado = processar(entrada)

    print(resultado)


def processar(texto):
    texto = texto.replace(" ", "")

    if texto == "":
        raise Exception("Entrada inválida: a string não pode ser vazia")

    numero_atual = ""
    resultado = 0
    sinal = "+"

    for i in texto:
        if i == "+" or i == "-":
            if numero_atual == "":
                raise Exception("Entrada inválida: operador sem número")

            if sinal == "+":
                resultado += int(numero_atual)
            else:
                resultado -= int(numero_atual)

            numero_atual = ""
            sinal = i

        elif i.isdigit():
            numero_atual += i

        else:
            raise Exception("Entrada inválida: caractere inválido, apenas números, '+' e '-' são permitidos")

    if numero_atual == "":
        raise Exception("Entrada inválida: operador sem número")

    if sinal == "+":
        resultado += int(numero_atual)
    else:
        resultado -= int(numero_atual)

    return resultado


if __name__ == "__main__":
    main()