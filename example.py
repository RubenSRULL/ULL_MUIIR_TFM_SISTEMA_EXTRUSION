import serial
import time
import threading


PORT = "/dev/ttyUSB0"
BAUDRATE = 115200


def read_serial(ser):
    while True:
        try:
            line = ser.readline()

            if line:
                print("RX:", line.decode(errors="replace").strip())

        except serial.SerialException as e:
            print("Error leyendo UART:", e)
            break


def main():
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
        write_timeout=1
    )

    print(f"Conectado a {PORT} @ {BAUDRATE}")
    print("Escribe comandos. Ejemplo: PING")
    print("CTRL+C para salir")

    reader = threading.Thread(target=read_serial, args=(ser,), daemon=True)
    reader.start()

    time.sleep(0.5)

    while True:
        cmd = input("> ").strip()

        if not cmd:
            continue

        ser.write((cmd + "\r\n").encode())
        ser.flush()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo")