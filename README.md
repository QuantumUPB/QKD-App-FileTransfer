# Unconditionally-Secure File Transfer Application

This application implements an unconditionally secure file transfer protocol enhanced by QKD.

## Features:

    Secure file transfer using One-Time Pad (OTP) encryption enhanced by QKD.
    Straighforward, user-friendly interface.

## Requirements:

    Python 3
    tkinter library for GUI elements
    numpy library for numerical computations
    json library for parsing JSON responses
    pillow library for image processing (used for the application icon)

To install all the required dependencies use

`pip3 install tkinter numpy json pillow`

    A point-to-point connection to a QKD device, and a way to get keys that can interface with QKGTTR module.

## Running the application:

    Run the script from the command line, specifying either "Alice" or "Bob" as the first argument depending on which party you want to run the application for: 

`python3 qotp.py Alice`

### How it works:

    The application prompts the user to choose between sending or receiving a file.
    If sending, the user selects a file to transfer. The application retrieves encryption keys from the server and encrypts the file using a One-Time Pad before sending it to the receiver through the broker server.
    If receiving, the application listens for incoming transmissions. If not actively sending a file, the application is passively listening for transmissions. When a file is sent to the user, a prompt to confirm the transmission appears. If accepted, the application retrieves decryption keys from the server and decrypts the received data before saving it as a file.
    Below you can find a diagram of how the unconditionally secure transmissions work.

