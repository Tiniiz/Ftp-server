import socket
import os
import shutil
import csv
import re

dirname = os.path.join(os.getcwd(), 'docs')
END_FLAG = b"$$STREAM_FILE_END_FLAG$$"
FAIL_FLAG = b'$FAILED$'
PORT = 6161
global_root = os.path.join(os.getcwd())
usersfile = os.path.join(global_root, "users.csv")
log_file = os.path.join(global_root, "log.txt")

def get_size(start_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size

def log_print(*strings):
    print(*strings)
    with open(log_file, "a") as logfile:
        logfile.write(" ".join([str(item) for item in strings]) + "\n")


def authorization(message):
    global usersfile, global_root
    login, message = message.split("=login", 1)
    password, message = message.split("=password", 1)
    current_directory, message = message.split("=cur_dir", 1)
    size, message = message.split("=file_size", 1)
    if login == password == "admin":
        user_root = global_root
    else:
        user_root = os.path.join(global_root, login)
        with open(usersfile, "a+", newline="") as csvfile:
            csvfile.seek(0, 0)
            reader = csv.reader(csvfile, delimiter=";")
            for line in reader:
                if line[0] == login:
                    if line[1] == password:
                        break
                    else:
                        return None
            else:
                writer = csv.writer(csvfile, delimiter=";")
                writer.writerow([login, password])

        try:
            os.makedirs(user_root)
        except FileExistsError:
            pass

    return user_root, current_directory, message, size


def process(req):
    req = authorization(req)
    if req:
        user_root, current_directory, req, size = req
        req, *dir_ = req.split()
        path = [path_decoder(user_root, current_directory, item) for item in dir_]
        if not path:
            path = [""]
        # print("#####################", req)
        if req == 'pwd':
            return pwd(current_directory)
        elif req == 'ls':
            return ls(os.path.join(user_root, current_directory[1:]))
        elif req == "cd":
            return cd(path[0], current_directory, user_root)
        elif req == 'mkdir':

            return mkdir(path[0])
        elif req == 'rmtree':
            return rmtree(path[0])
        elif req == 'touch':
            return touch(path[0])
        elif req == 'remove':
            return remove(path[0])
        elif req == 'cat':
            return cat(path[0])
        elif req == 'rename':
            return rename(*path[:2])
        elif req == "get_file":
            return get_file(path[0])
        elif req == "send_file":
            return send_file(path[0], user_root, size)
        else:
            return 'bad request'
    else:
        return "Incorrect password"


def path_decoder(root, current, dir_):
    if current == "\\" and dir_[:2] == "..":

        return root + dir_[2:]
    elif dir_[0] in ["\\", "/"]:
        dir_ = re.sub(r"^[\\/]+", "", dir_)
        log_print(dir_)
        return os.path.join(root, dir_)
    else:
        return os.path.join(root, current[1:], dir_)


def try_decorator(path_func):
    def wrapper(*path):
        try:
            returned = path_func(*path)
            if returned == None:
                return "successfully"
            else:
                return returned
        except FileNotFoundError:
            return (f'Invalid path')
        except FileExistsError:
            return (f'Has already exist')
        except PermissionError:
            return f"Permission denied"

    return wrapper


def pwd(dirname):
    return os.path.join(dirname)


def ls(path):
    return '\n\r'.join(os.listdir(path))


def cd(path, current, root):
    try:
        os.chdir(path)
    except:
        return current
    return os.getcwd().replace(root, "") + "\\"


@try_decorator
def mkdir(path):
    os.makedirs(path)


@try_decorator
def rmtree(path):
    shutil.rmtree(path)


@try_decorator
def remove(path):
    os.remove(path)


@try_decorator
def touch(path):
    with open(path, 'x'):
        pass


@try_decorator
def cat(path):
    with open(path, "r") as file:
        return "\n\r".join(file.readlines())


@try_decorator
def rename(path1, path2):
    os.rename(path1, path2)


def get_file(path):
    global conn, END_FLAG, FAIL_FLAG
    try:
        with open(path, "rb") as bytefile:
            while read_bytes := bytefile.read(1024):
                conn.send(read_bytes)

    except FileNotFoundError:
        returned = b'Invalid path' + FAIL_FLAG
    except PermissionError:
        returned = b"Permission denied" + FAIL_FLAG
    else:
        returned = END_FLAG
    log_print("Has been sent")
    return returned


def send_file(path, root, size):
    global conn, END_FLAG, FAIL_FLAG
    available = pow(2, 20) * 10 - get_size(root)  # 10Mb for each user
    print(available, int(size))
    if available < int(size):
        return "Not enough disk space!"
    else:
        conn.send(b"$ENOUGHT$")
    flag_finder = conn.recv(1024)
    with open(path, "wb") as bytefile:
        while True:
            if END_FLAG in flag_finder:
                bytefile.write(flag_finder.replace(END_FLAG, b""))
                break
            else:
                bytefile.write(flag_finder)
                flag_finder = conn.recv(1024)
    log_print("Has been received")
    return "uploaded successfully"


sock = socket.socket()
sock.bind(('', PORT))
sock.listen()
log_print("Прослушиваем порт", PORT)

while True:
    conn, addr = sock.accept()

    request = conn.recv(1024).decode()
    print(request)

    response = process(request)
    conn.send(response.encode())
    log_print("request:", request)

    response = process(request)
    log_print("response:", response)
    if not response:
        response = "\00"
    try:
        conn.send(response.encode())
    except AttributeError:
        conn.send(response)
    # log_print("responsed")
conn.close()
