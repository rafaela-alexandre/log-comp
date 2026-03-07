import sys


def main():
    entrada = "789   +345  -    123"   # sys.argv[1]
    resultado = processar(entrada)
    print(resultado)


def processar(texto):
    texto = texto.strip()

    if texto == "":
        raise Exception("entrada invalida")

    numero_atual = ""
    resultado = 0
    sinal = "+"
    ultimo = "inicio"

    for i in texto:
        if i == " ":
            if numero_atual != "":
                ultimo = "numero_espacado"
            continue

        elif i.isdigit():
            if ultimo == "numero_espacado":
                raise Exception("entrada invalida")
            numero_atual += i
            ultimo = "numero"

        elif i == "+" or i == "-":
            if numero_atual == "":
                raise Exception("entrada invalida")

            if sinal == "+":
                resultado += int(numero_atual)
            else:
                resultado -= int(numero_atual)

            numero_atual = ""
            sinal = i
            ultimo = "operador"

        else:
            raise Exception("entrada invalida")

    if numero_atual == "":
        raise Exception("entrada invalida")

    if sinal == "+":
        resultado += int(numero_atual)
    else:
        resultado -= int(numero_atual)

    return resultado


if __name__ == "__main__":
    main()