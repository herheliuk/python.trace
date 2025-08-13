#!/usr/bin/env python3

from sys import stdin, stdout, exit

try:
    from msvcrt import getch
except:
    from termios import tcgetattr, tcsetattr, TCSADRAIN
    from tty import setraw
    def getch():
        fd = stdin.fileno()
        old = tcgetattr(fd)
        try:
            setraw(fd)
            char = stdin.read(1)
            return char.encode()
        finally:
            tcsetattr(fd, TCSADRAIN, old)

def await_command(prompt):
    stdout.write(prompt)
    stdout.flush()
    buffer = b""

    while True:
        match getch():
            # Digits
            case char if char.isdigit():
                buffer += char
                stdout.write(char.decode())
                stdout.flush()

            # Enter
            case b"\r" | b"\n":
                stdout.write("\n")
                text = buffer.decode()
                if text.isdigit():
                    return 'jump', text
                return 'next', None

            # Backspace
            case b"\x08" | b"\x7f":
                if not buffer:
                    stdout.write("\n")
                    return 'prev', None
                buffer = buffer[:-1]
                stdout.write("\b \b")
                stdout.flush()

            # Ctrl + C | ESC
            case b"\x03" | b"\x1b":
                stdout.write("\n")
                exit(1)

if __name__ == '__main__':
    while True:
        code, result = await_command("> ")

        match code:
            case 'next':
                print("NEXT LINE")
            case 'prev':
                print("PREV LINE")
            case 'jump':
                print(f"JUMP LINE {int(result)}")
