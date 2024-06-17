#!/bin/python3
import subprocess
import json
import time
import asyncio
import hashlib
import socket
import numpy as np
import threading
import sys
from tqdm import tqdm
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter import messagebox, Tk, Button, Toplevel
from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk

import sys
import signal

lock = asyncio.Lock()

def signal_handler(sig, frame):
    print("\nProgram interrupted. Exiting gracefully...")
    sys.exit(0)

class KeyContainer:
    def __init__(self, key, key_ID):
        self.key = key
        self.key_ID = key_ID


encrypt_curl_command = "curl -Ss --cert your.crt --key your.key --cacert your-ca.crt -k https://141.85.241.65:11443/api/v1/keys/UPB-BC-UPBC/enc_keys"
decrypt_curl_command = "curl -Ss --cert your.crt --key your.key --cacert your-ca.crt -k https://141.85.241.65:22443/api/v1/keys/UPB-BC-UPBR/dec_keys -X POST -H 'Content-Type:application/json'"

broker = "141.85.224.172"
sender_ports = {
    "Alice": 12344,
    "Bob": 12346
}

receiver_ports = {
    "Alice": 12345,
    "Bob": 12347
}

seg_length = 220
key_length = 184

# Define the path to the icon
icon_path = './LogoIQC.png'

whoami = 'Alice'

def show_progress_bar(title, max_value):
    progress_root = Tk()
    progress_root.title(title)

    # Set the icon
    # progress_root.iconphoto(False, PhotoImage(file=icon_path))

    progress_root.geometry("500x300+300+200")

    # label = Label(progress_root, text=title)
    # label.pack(pady=10)

    progress = ttk.Progressbar(progress_root, orient=HORIZONTAL, length=300, mode='determinate')
    progress.pack(pady=20)

    # Add text label below the progress bar
    # text_label = Label(progress_root, text="Processing...")
    # text_label.pack(pady=10)

    # # Create a frame to hold the labels at the bottom
    # bottom_frame = Frame(progress_root)
    # bottom_frame.pack(side=BOTTOM, pady=10)

    # # Place the labels next to each other in the bottom frame
    # instruction_label1 = Label(bottom_frame, text="Unconditionally-secure file transfer application\nDeveloped by the Quantum Team @ UPB")
    # instruction_label1.pack(side=LEFT, pady=5)

#    # Load and place the icon in the lower right corner
#     icon = Image.open(icon_path)
#     icon = icon.resize((45, 25), Image.LANCZOS)  # Resize the icon to 50x50 pixels
#     icon = ImageTk.PhotoImage(icon)
#     icon_label = Label(progress_root, image=icon)
#     icon_label.image = icon  # Keep a reference to avoid garbage collection
#     icon_label.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)  # Adjust 'x' and 'y' for padding

    return progress_root, progress

def ask_user():
    def send_file():
        nonlocal user_choice
        user_choice[0] = True
        top.title("Sending file")
        root.quit()

    user_choice = [None]  # Use a mutable type to allow modification within inner function
    root = Tk()
    root.withdraw()  # to hide the main window
    top = Toplevel(root)
    top.title("Unconditionally Secure File Transfer - " + whoami)

    # Set the icon
    top.iconphoto(False, PhotoImage(file=icon_path))

    # Set window size (width x height + offsetx + offsety)
    top.geometry("500x200+300+200")

    send_button = Button(top, text="Send file", command=send_file)
    send_button.pack(fill="both", expand=True, pady=10)

    # Add text label below the progress bar
    text_label = Label(top, text="Listening for incoming transmissions")
    text_label.pack(pady=10)

    # Create a frame to hold the labels at the bottom
    bottom_frame = Frame(top)
    bottom_frame.pack(side=BOTTOM, pady=10)

    # Place the labels next to each other in the bottom frame
    instruction_label1 = Label(bottom_frame, text="Unconditionally-secure file transfer application\nDeveloped by the Quantum Team @ UPB")
    instruction_label1.pack(side=LEFT, pady=5)

   # Load and place the icon in the lower right corner
    icon = Image.open(icon_path)
    icon = icon.resize((45, 25), Image.LANCZOS)  # Resize the icon to 50x50 pixels
    icon = ImageTk.PhotoImage(icon)
    icon_label = Label(top, image=icon)
    icon_label.image = icon  # Keep a reference to avoid garbage collection
    icon_label.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)  # Adjust 'x' and 'y' for padding

    root.mainloop()
    root.destroy()  # necessary to close the window completely

    return user_choice[0], root, send_button

async def send_file():
    async with lock:
        file_path = askopenfilename()
        message = ""
        file_name = file_path.split('/')[-1]
        print("Sending: " + file_name)
        with open(file_path, "rb") as file:
            message = file.read()

        number_of_segments = int(np.ceil(len(message) / seg_length))

        progress_root, progress = show_progress_bar("Sending file", number_of_segments)
        progress['maximum'] = number_of_segments
        progress_root.update_idletasks()

        # Send the number of segments needed for the message
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Connect to the server
            client_socket.connect((broker, sender_ports[whoami]))

            # Await for receiver to connect
            print("Awaiting for the receiver to connect.")
            goahead = client_socket.recv(1024)
            if not goahead:
                print("Connection closed by broker")
                client_socket.close()
                return

            # Convert the number of segments to bytes
            encrypted_message_bytes = bytes(str(len(message)) + "/" + file_name, 'utf-8')

            # Send the metadata
            client_socket.sendall(encrypted_message_bytes)
            print("Metadata sent successfully!")

            print("Awaiting for the receiver to accept.")
            response = client_socket.recv(1024)
            if not response or str(response, 'utf-8') != "ok":
                print("Transmission not accepted by receiver")
                client_socket.close()
                return
        except ConnectionRefusedError:
            print("Connection refused. Make sure the server is running.")
            client_socket.close()
            return

        # Execute the curl command periodically and accumulate keys
        for i in tqdm(range(number_of_segments)):
            progress['value'] = i
            progress_root.update_idletasks()

            accumulated_keys = bytearray()
            key_objects = []
            for _ in range(5):
                output_bytes = subprocess.check_output(encrypt_curl_command, shell=True)

                # Decode the output to a string using UTF-8 encoding
                output = output_bytes.decode('utf-8')

                # Parse the JSON response into a Python dictionary
                response = json.loads(output)

                # Extract the key and key_ID values
                keys = response['keys']
                for key_data in keys:
                    key = key_data['key']
                    key_ID = key_data['key_ID']
                    key_object = KeyContainer(key, key_ID)
                    key_objects.append(key_object)

                    # Accumulate the key bytes
                    accumulated_keys.extend(bytearray(key, 'utf-8'))

                # Delay execution for 100 milliseconds
                # time.sleep(0.1)

            batch_len = min(len(accumulated_keys), len(message))

            # Perform OTP encryption by XORing the message with the accumulated keys
            encrypted_message = bytearray()
            for i in range(batch_len):
                encrypted_byte = message[i] ^ accumulated_keys[i]
                encrypted_message.append(encrypted_byte)

            # Print the encrypted message
            key_ids_list = []
            for key_obj in key_objects:
                key_ids_list.append(key_obj.key_ID)

            message = message[batch_len:]

            try:
                # Convert the encrypted message to bytes
                encrypted_message_bytes = bytes(encrypted_message)

                # Send the encrypted message
                client_socket.sendall(encrypted_message_bytes)
            except ConnectionRefusedError:
                print("Connection refused. Make sure the server is running.")

            try:
                # Convert the key_ids to bytes
                combined_key_ids = '|'.join(key_ids_list)
                key_ids_bytes = combined_key_ids.encode('utf-8')

                # Send the key ids
                client_socket.sendall(key_ids_bytes)
            except ConnectionRefusedError:
                print("ECONNREFUSED")

            ack = client_socket.recv(1024)

        progress['value'] = number_of_segments
        progress_root.update_idletasks()
        progress_root.destroy()
        client_socket.close()
        print("MD5 Hash of original message:", hashlib.md5(message).hexdigest())

async def receive_file():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((broker, receiver_ports[whoami]))
    except ConnectionRefusedError:
        print("Connection refused. Make sure the broker is running.")
        client_socket.close()
        return

    print("Awaiting for sender to begin transmission.")
    metadata_raw = client_socket.recv(1024)
    msg_len = int(metadata_raw.split("/".encode('utf-8'))[0])
    file_path = str(metadata_raw.split("/".encode('utf-8'))[-1], 'utf-8')

    async with lock:
        if not messagebox.askyesno("File Transfer", "Do you want to receive file " + file_path + "?"):
            client_socket.send(bytes("reject", 'utf-8'))
            client_socket.close()
            return
        file_path = asksaveasfilename(initialfile=file_path, filetypes=[("All files", "*.*")])
        remaining_len = msg_len
        seg_no = int(np.ceil(msg_len / seg_length))
        print("Payload length: " + str(msg_len) + " bytes.")
        accumulated_keys = bytearray()
        encrypted_message = bytearray()
        client_socket.send(bytes('ok', 'utf-8'))

        progress_root, progress = show_progress_bar("Receiving file", seg_no)
        progress['maximum'] = seg_no
        progress_root.update_idletasks()

        print(seg_no)

        for i in tqdm(range(seg_no)):
            progress['value'] = i
            progress_root.update_idletasks()

            # Receive data from the client
            new_data = client_socket.recv(min(seg_length, remaining_len))
            encrypted_message.extend(new_data)
            remaining_len -= len(new_data)

            # Receive key ids from the client
            key_ids_enc = client_socket.recv(key_length)

            if encrypted_message:
                # Perform further processing on the encrypted message as needed
                key_ids = key_ids_enc.decode('utf-8').split('|')

                for key_id in key_ids:
                    complete_command = decrypt_curl_command + " -d '{ \"key_IDs\":[{ \"key_ID\": \"" + key_id + "\" }] }'"
                    output_bytes = subprocess.check_output(complete_command, shell=True)
                    output = output_bytes.decode('utf-8')
                    response = json.loads(output)
                    print(response)

                    keys = response['keys']
                    for key_data in keys:
                        key = key_data['key']
                        accumulated_keys.extend(bytearray(key, 'utf-8'))
                        
            client_socket.send(bytes('ok', 'utf-8'))

        # Close the client socket
        client_socket.close()

        decrypted_message = bytearray()
        for i in range(len(encrypted_message)):
            decrypted_byte = encrypted_message[i] ^ accumulated_keys[i]
            decrypted_message.append(decrypted_byte)

        md5_hash = hashlib.md5(decrypted_message).hexdigest()
        print("MD5 hash of original message:", md5_hash)

        progress['value'] = seg_no
        progress_root.update_idletasks()
        progress_root.destroy()

        with open(file_path, "wb") as file:
            file.write(decrypted_message)

def on_closing():
    print("Window closed. Exiting gracefully...")
    sys.exit(0)

async def continuous_receive_file():
    while True:
        await receive_file()

def start_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./qotp.py [Alice/Bob]")
        sys.exit(1)

    whoami = sys.argv[1]

    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)
    # Create a new asyncio event loop
    loop = asyncio.new_event_loop()
    
    # Start the asyncio event loop in a separate thread
    asyncio_thread = threading.Thread(target=start_asyncio_loop, args=(loop,), daemon=True)
    asyncio_thread.start()

    # Schedule the continuous_receive_file function to run in the asyncio event loop
    asyncio.run_coroutine_threadsafe(continuous_receive_file(), loop)

    while True:
        operation, root, send_button = ask_user()
        send_loop = asyncio.new_event_loop()
        send_loop.run_until_complete(send_file()) 
