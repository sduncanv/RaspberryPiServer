import time
import math
import busio
import board
import socket
import threading
import adafruit_mcp4725
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from firebase_module import initialize_firebase, write_something_data, get_current_datetime

# Inicializar Firebase
cred_path = "credential.json"
database_url = "https://database-holo-lens-valve-default-rtdb.firebaseio.com/"
initialize_firebase(cred_path, database_url)

# Create I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Create MCP4725 DAC instance
dac = adafruit_mcp4725.MCP4725(i2c, address=0x60)

# Create ADS1015 ADC instance
ads = ADS.ADS1015(i2c, address=0x48)
chan = AnalogIn(ads, ADS.P0) # Assuming distance sensor output is connected to A0
ads.gain = 1

# Server configuration
HOST = "128.46.87.232" # Server IP
PORT = 9061

SLIDER_VALUE = 0
REMAPPED_VOLTAGE_VALUE = 0

# Function to remap the ADC voltage
def remap_voltage(adc_value, adc_max_value=1023, input_max_voltage=3.18, output_min=0.318, output_max=1.06):

    input_voltage = (adc_value / adc_max_value) * input_max_voltage
    output_voltage = output_min + ((input_voltage / input_max_voltage) * (output_max - output_min))

    return output_voltage

connected_clients = [] # Lista para almacenar los clientes conectados

# Function to handle client connections
def handle_client(client_socket):
    global SLIDER_VALUE
    global REMAPPED_VOLTAGE_VALUE
    connected_clients.append(client_socket)

    with client_socket:

        print(f"New connection from {client_socket.getpeername()}")
        buffer = ""
        Color = False

        try:
            while True:
                data = client_socket.recv(256).decode('utf-8')

                if not data:
                    print("No message received, closing connection.")
                    break

                print(f"Received: {data}")

                # Process the received message
                buffer += data
                messages = buffer.split("\n")
                buffer = messages.pop()
                
                for client in connected_clients:
                    if client != client_socket:
                        client.sendall(data.encode('utf-8'))

                for message in messages:

                    if message.strip() == "Ping":
                        response = "Pong"

                    elif message.strip() == "Data":

                        # Read the voltage from the ADS1015 sensor
                        current_voltage = chan.voltage
                        print(f"ADC Voltage: {current_voltage:.2f} V")

                        # Remap the voltage
                        remapped_voltage = remap_voltage(current_voltage * 4096 / 3.3)  # Assuming 3.3 V system
                        print(f"Remapped Voltage: {remapped_voltage:.2f} V")

                        # Send the response with the voltage data
                        response = f"ADC Voltage: {current_voltage:.2f} V; Remapped Voltage: {remapped_voltage:.2f} V"

                    elif message.strip().lstrip('\ufeff') == "GET_STATE":

                        print(f"1. response ----------> {'STATE'};{REMAPPED_VOLTAGE_VALUE};{SLIDER_VALUE}")
                        response = f"{'STATE'};{REMAPPED_VOLTAGE_VALUE};{SLIDER_VALUE}" + "\n"
                        print(f'2. response ----------> {response}')

                    elif len(message.strip()) <= 4 and len(message.strip()) >= 1:
                        print(f"----- {message}")

                        # Process numeric message to adjust DAC output and read ADC
                        response = "[Server] Received: " + message + "\n"
                        print('Setting voltage based on received message!')

                        # Set the voltage in DAC based on the received value
                        voltage = math.floor((float(message.strip().lstrip('\ufeff')) * 10 * 50)) + 600
                        dac.raw_value = voltage # Set the DAC output
                        SLIDER_VALUE = float(message.strip().lstrip('\ufeff'))

                        # Read Sthe voltage from the ADC
                        current_voltage = chan.voltage
                        print(f"ADC Voltage: {chan.voltage:.2f} V")

                        # Remap the voltage
                        # remapped_voltage = remap_voltage(current_voltage * 2048 / 3.3) # Assuming 3.3 V system
                        remapped_voltage = 0
                        REMAPPED_VOLTAGE_VALUE = remapped_voltage
                        print(f"REMAPPED_VOLTAGE_VALUE ----------> {REMAPPED_VOLTAGE_VALUE}")

                        # Send the response with the ADC and DAC data
                        response = f"{remapped_voltage:.2f};{SLIDER_VALUE:.2f}"+ "\n"
                        print(f'response ----------> {response}')

                        # Get current datetime
                        formatted_date = get_current_datetime()

                        # Create data to upload to Firebase
                        #holo_data = {
                            #'Levels': dac.raw_value,
                            #'Voltage': message.strip(),
                            #'Distance': (chan.voltage*14.235+8.6188)/10
                        #}

                        # Upload data to Firebase
                        # write_something_data(formatted_date, holo_data)

                    else:
                        #response = "[Server] Received: no string :" + message + "\n"
                        response = "" + "\n"

                    # Get current datetime
                    #formatted_date = get_current_datetime()

                    # Create data to upload to Firebase
                    #holo_data = {
                        #'Levels': dac.raw_value,
                        #'Voltage': message.strip(),
                        #'Distance': chan.voltage
                    #}
                    #print(holo_data)+ "\n"

                    # Upload data to Firebase
                    #write_something_data(formatted_date, holo_data)

                    # Send the response to the client
                    client_socket.sendall(response.encode('utf-8'))

        except ConnectionResetError:
            print(f"Connection reset by {client_socket.getpeername()}")
        except Exception as e:
            print(f"Error handling client {client_socket.getpeername()}: {e}")
        finally:
            print(f"Connection closed for {client_socket.getpeername()}")


# Function to start the server
def start_server():

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"Server listening on {HOST}:{PORT}")

        while True:
            client_socket, addr = server_socket.accept()
            client_handler = threading.Thread(target=handle_client, args=(client_socket,))
            client_handler.start()


if __name__ == "__main__":
    start_server()


