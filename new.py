#!/bin/python3

import sys
import socket
import getopt
import threading
import subprocess
import time
import selectors

selector = selectors.DefaultSelector()

# define some global variables
listen = False
command = False
upload = False
execute = ""
target = ""
upload_destination = ""
port = 0

def usage():
    print("BHP Net Tool")
    print("\nUsage: bhpnet.py -t target_host -p port")
    print("-l --listen - listen on [host]:[port] for incoming connections")
    print("-e --execute=file_to_run - execute the given file upon receiving a connection")
    print("-c --command - initialize a command shell")
    print("-u --upload=destination - upon receiving connection upload a file and write to [destination]")
    print("\nExamples: ")
    print("bhpnet.py -t 192.168.0.1 -p 5555 -l -c")
    print("bhpnet.py -t 192.168.0.1 -p 5555 -l -u=c:\\target.exe")
    print('bhpnet.py -t 192.168.0.1 -p 5555 -l -e="cat /etc/passwd"')
    print("echo 'ABCDEFGHI' | ./bhpnet.py -t 192.168.11.12 -p 135")
    sys.exit(0)

def client_sender():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # connect to our target host
        print(f"Connecting to {target}:{port}..")
        client.connect((target, port))
        selector.register(client, selectors.EVENT_READ, data=None)

        while True:

            # wait for data in the client socket to read
            events = selector.select()

            # after data is ready to read, start reading 
            for key, _ in events:
                if key.fileobj == client:
                    data = client.recv(4096)
                    if data:
                        print(data.decode(), end="")
                    else:
                        print("Aborting connection...")
                        sys.exit(1)

            # wait for more input
            buffer = input("")
            buffer += "\n"

            # send it off
            client.sendall(buffer.encode())

    except Exception as e:
        print(f"[*] Exception! Exiting. {e}")

    # tear down the connection
    client.close()

def server_loop():
    global target

    # if no target is defined, we listen on all interfaces
    if not len(target):
        target = "0.0.0.0"

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((target, port))

    server.listen(5)


    while True:
        # print(f"Waiting for client on port {target}:{port}...")
        client_socket, addr = server.accept()
        print(f"Accepted from {addr}")
        time.sleep(1.0)

        # spin off a thread to handle our new client
        client_thread = threading.Thread(target=client_handler, args=(client_socket,))
        client_thread.start()

def run_command(command: str):
    # trim the newline
    command = command.rstrip()

    # run the command and get the output back
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
    except Exception as e:
        output = f"Failed to execute command: {e}\r\n"

    # send the output back to the client
    return output

def client_handler(client_socket: socket.socket):
    global upload
    global execute
    global command

    # check for upload
    if len(upload_destination):
        # read in all of the bytes and write to our destination
        file_buffer = ""

        # keep reading data until none is available
        while True:
            data = client_socket.recv(1024)

            if not data:
                break
            else:
                file_buffer += data.decode()

        # now we take these bytes and try to write them out
        try:
            with open(upload_destination, "wb") as file_descriptor:
                file_descriptor.write(file_buffer.encode())

            # acknowledge that we wrote the file out
            client_socket.send(f"Successfully saved file to {upload_destination}\r\n".encode())
        except Exception as e:
            client_socket.send(f"Failed to save file to {upload_destination}\r\n".encode())

    # check for command execution
    if len(execute):
        # run the command
        output = run_command(execute)
        client_socket.send(output.encode())

    # now we go into another loop if a command shell was requested
    if command:
        # print("on client handler with command")
        while True:
            # show a simple prompt
            client_socket.sendall("<BHP:#> ".encode())
            print("sent success..")

            # now we receive until we see a linefeed (enter key)
            cmd_buffer = ""
            while "\n" not in cmd_buffer:
                cmd_buffer += client_socket.recv(1024).decode()

            # run command and get the result in response
            response = run_command(cmd_buffer)

            # send back the response
            if isinstance(response, str):
                client_socket.sendall(response.encode("utf-8"))
            else:
                print(type(response))
                client_socket.sendall(response)


def main():
    global listen
    global port
    global execute
    global command
    global upload_destination
    global target

    if not len(sys.argv[1:]):
        usage()

    # read the commandline options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hle:t:p:cu:", 
                                    ["help", "listen", "execute", "target", "port", "command", "upload"])
    except getopt.GetoptError as err:
        print(str(err))
        usage()

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o in ("-l", "--listen"):
            listen = True
        elif o in ("-e", "--execute"):
            execute = a
        elif o in ("-c", "--command"):
            command = True
        elif o in ("-u", "--upload"):
            upload_destination = a
        elif o in ("-t", "--target"):
            target = a
        elif o in ("-p", "--port"):
            port = int(a)
        else:
            assert False, "Unhandled Option"

    # are we going to listen or just send data from stdin?
    if not listen and len(target) and port > 0:
        # send data off
        client_sender()

    # we are going to listen and potentially upload things, execute commands, and drop a shell back
    # depending on our command line options above
    if listen:
        server_loop()

main()


