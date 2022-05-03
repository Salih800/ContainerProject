import base64
import datetime
import glob
import hashlib
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

hostname = subprocess.check_output(["hostname"]).decode("utf-8").strip("\n")
requirements = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/requirements.txt"

log_file_name = f"{hostname}.log"
if os.path.isfile(log_file_name):
    with open(log_file_name, "r+") as log_file:
        log_file.write("\n")

logger = logging.getLogger("mylog")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(log_file_name)
fmt = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')
handler.setFormatter(fmt)
logger.addHandler(handler)

logger.debug("")
logger.info("System Started.")

try:
    import geopy.distance
    import pynmea2
    import requests
    import imutils
    import serial
    import cv2

except ModuleNotFoundError as module:
    logger.warning("Module not found: ", module.name)
    time.sleep(30)
    logger.info("Trying to install requirements.txt")
    if subprocess.check_call(["pip", "install", "-r", requirements]) == 0:
        logger.info("Modules installed")
    else:
        logger.warning("Module install failed!")

def hash_check(file, blocksize=None):
    if blocksize is None:
        blocksize = 65536

    md5 = hashlib.md5()
    with open(file, "rb") as f:
        for block in iter(lambda: f.read(blocksize), b""):
            md5.update(block)
    return md5.hexdigest()


def get_date():
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')


def error_handling():
    exception_type, exception_object, exception_traceback = sys.exc_info()
    line_number = exception_traceback.tb_lineno
    logger.error(f"Type: {exception_type}\tObject: {exception_object}\tLine number: {line_number}")


def restart_system(restart_type=None, why=None):
    if restart_type == "info":
        logger.info(f"Restarting the system: {why}")
    if restart_type == "warning":
        logger.warning(f"Restarting the system: {why}")
    if restart_type == "error":
        logger.error(f"Restarting the system: {why}")
    subprocess.call(["sudo", "reboot"])

def write_json(json_data, json_file_name='locations.json'):
    json_file_path = f"{files_folder}/{json_file_name}"
    try:
        if not os.path.isfile(json_file_path):
            data = [json_data]
        else:
            data = read_json(json_file_path)
            data.append(json_data)
        json.dump(data, open(json_file_path, "w"))

    except:
        error_handling()


def read_json(json_file):
    try:
        data = json.load(open(json_file, "r"))
    except json.decoder.JSONDecodeError as json_error:
        logger.warning(f"JSONDecodeError happened at {json_file}: {json_error.pos}. Trying to save the file...")
        data = json.loads(open(json_file).read()[:json_error.pos])
        logger.info(f"{len(data)} file info saved.")
    return data


def upload_data(file_type, file_path=None, file_data=None):
    # timeout_to_upload = 120
    try:
        if file_type == "log":
            rclone_log = subprocess.check_call(
                ["rclone", "move", file_path,
                 f"gdrive:Python/ContainerFiles/logs/"])
            if not os.path.isfile(file_path):
                logger.info(f"{file_path} uploaded to gdrive.")

            if os.path.isfile(file_path):
                logger.warning(f"{file_path} log file couldn't uploaded! Rclone Status: {rclone_log}")

        elif file_type == "video":
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as video:
                files = {'file': (file_name, video, 'multipart/form-data', {'Expires': '0'})}

                date_of_file = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                file_date = date_of_file.strftime("%Y-%m-%d")
                file_time = date_of_file.strftime("%H:%M:%S")
                file_upload_type = "garbagedevice"

                url_to_upload = url_harddrive + f"type={file_upload_type}&date={file_date}&time={file_time}"
                result = MyRequestsClass(request_type="post", url=url_to_upload, files=files)
                status_code = result.status_code

            if status_code == 200:
                status = result.result.json()["status"]
                if status == "success":
                    uploaded_file = result.result.json()["filename"]
                    # file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                    file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                    file_data = {"file_name": uploaded_file, "date": f"{date_of_file}",
                                 "lat": file_lat, "lng": file_lng, "id": file_id}

                    my_file_data = {"device_name": hostname, "device_type": device_type, "file_id": uploaded_file,
                                    "date": f"{date_of_file}", "lat": file_lat, "lng": file_lng, "location_id": file_id}
                    write_json(my_file_data, "uploaded_files.json")

                    result = MyRequestsClass(request_type="post", url=url_image + hostname, json=file_data)
                    if not result.status_code == 200:
                        logger.warning(f"Video Name couldn't uploaded! "
                                       f"Status Code: {result.status_code}:{result.error}")
                        write_json(file_data, "uploaded_images.json")

                    os.remove(file_path)

                else:
                    logger.error(f"Video file couldn't uploaded! "
                                 f"Status Code: {result.status_code}\tStatus: {result.error}")

            else:
                logger.warning(f"Video file couldn't uploaded! Status Code: {status_code}:{result.error}")

        elif file_type == "location":
            result = MyRequestsClass(request_type="post", url=url_location + hostname, json=file_data)
            if not result.status_code == 200:
                logger.warning(f"location couldn't uploaded! "
                               f"Status Code: {result.status_code}:{result.error}")
                write_json(file_data, "locations.json")

        elif file_type == "locations":
            # with open(file_path) as file:
            location_json = read_json(file_path)
            result = MyRequestsClass(request_type="post", url=url_location + hostname, json=location_json)
            if result.status_code == 200:
                logger.info("locations.json uploaded")
                os.remove(file_path)
            else:
                logger.warning(f"locations.json upload warning: {result.status_code}:{result.error}")

        elif file_type == "uploaded_videos":
            # with open(file_path) as file:
            videos_json = read_json(file_path)
            result = MyRequestsClass(request_type="post", url=url_image + hostname, json=videos_json)
            if result.status_code == 200:
                logger.info("uploaded_videos.json uploaded")
                os.remove(file_path)
            else:
                logger.warning(f"uploaded_videos.json upload warning: {result.status_code}")

        elif file_type == "uploaded_files":
            if os.path.getsize(file_path) / 1024 > 100:
                logger.info(f"Trying to upload {file_path}")
                uploaded_files_date = datetime.datetime.now().strftime("%Y-%m-%d")
                uploaded_files_time = datetime.datetime.now().strftime("%H-%M-%S")
                uploaded_files_name = f"{uploaded_files_date}_{uploaded_files_time}_{hostname}.json"
                shutil.copy(file_path, uploaded_files_name)
                rclone_call = subprocess.check_call(
                    ["rclone", "move", uploaded_files_name, f"gdrive:Python/ContainerFiles/files/"])
                if os.path.isfile(uploaded_files_name):
                    os.remove(uploaded_files_name)
                    logger.warning(f"Rclone failed with {rclone_call}")
                else:
                    logger.info(f"'uploaded_files.json' uploaded to gdrive. Rclone returned: {rclone_call}")
                    os.remove(file_path)

    except:
        error_handling()


def get_folder_size(path_to_folder):
    size = 0
    for path, dirs, files in os.walk(path_to_folder):
        for f in files:
            fp = os.path.join(path, f)
            size += os.path.getsize(fp)
    return size


def file_size_unit(size: int, elapsed_time):
    for unit in ("B", "K", "M", "G", "T"):
        if size < 1024:
            break
        size /= 1024
    return f"{size:.1f}{unit}", f"{size/elapsed_time:.2f}{unit}/s"


def check_folder():
    try:
        upload_start_time = time.time()
        files_list = os.listdir(files_folder)
        upload_start_size = get_folder_size(files_folder)
        if len(files_list) > 1:
            logger.info(f"Files in folder: {len(files_list)}")
        for file_to_upload in files_list:
            if connection:
                if file_to_upload.endswith(".log"):
                    upload_data(file_type="log", file_path=f"{files_folder}/{file_to_upload}")
                if os.path.isfile(f"{files_folder}/uploaded_files.json"):
                    upload_data(file_type="uploaded_files", file_path=f"{files_folder}/uploaded_files.json")
                if os.path.isfile(f"{files_folder}/uploaded_videos.json"):
                    upload_data(file_type="uploaded_videos", file_path=f"{files_folder}/uploaded_videos.json")
                if os.path.isfile(f"{files_folder}/locations.json"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.json")
                if file_to_upload.endswith(".mp4"):
                    upload_data(file_type="video", file_path=f"{files_folder}/{file_to_upload}")
        total_uploaded_file = len(files_list) - len(os.listdir(files_folder))
        if total_uploaded_file > 0:
            upload_end_time = round(time.time() - upload_start_time, 2)
            upload_end_size, ratio = file_size_unit(upload_start_size - get_folder_size(files_folder), upload_end_time)
            logger.info(f"{total_uploaded_file} files and {upload_end_size} "
                         f"uploaded in {upload_end_time} seconds. Ratio: {ratio}")
        time.sleep(60)
    except:
        error_handling()


def listen_to_server():
    global hostname, server, server_msg, connection, stream, threadKill
    host = "93.113.96.30"
    port = 8181
    buff_size = 127
    alive_msg = b"$k$"

    try:
        stream = False
        logger.info("Trying to connect to Streaming Server")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (host, port)
        server.connect(server_address)
        server.settimeout(60)
        id_message = bytes("$id" + hostname + "$", "utf-8")
        server.sendall(id_message)
        logger.info(f"Id message sent to the Server: {id_message}")
        server.sendall(alive_msg)
        while True:
            logger.info("Listening server...")
            server_msg = server.recv(buff_size)
            if server_msg != b"":
                data_orig = server_msg.decode("utf-8")
                merge_msg = False
                messages = []
                new_msg = ""
                for d in data_orig:
                    if d == "$":
                        if not merge_msg:
                            merge_msg = True
                            continue
                        else:
                            merge_msg = False
                            messages.append(new_msg)
                            new_msg = ""
                    if merge_msg:
                        new_msg += d

                for command in messages:
                    if command == "start":
                        stream = True
                        logger.info("Start to stream command received.")
                        thread_list_folder = []
                        for thread_folder in threading.enumerate():
                            thread_list_folder.append(thread_folder.name)
                        if "opencv" not in thread_list_folder:
                            logger.info("Starting OpenCV")
                            threading.Thread(target=capture, name="opencv", daemon=True).start()

                    elif command == "stop":
                        stream = False
                        # threadKill = True
                        logger.info("Stop to stream command received.")
                    elif command == "k":
                        if not stream:
                            server.sendall(alive_msg)
                        # logger.info("Server is Online.")
                    else:
                        logger.warning(f"Unknown message from server: {command}")
                        time.sleep(5)
            else:
                logger.error(f"Empty byte from Server. Closing the connection!: Server Message: {server_msg}")
                server.close()
                break

    except socket.timeout:
        logger.warning("Server timeout in 60 seconds! Closing the connection.")
        stream = False
        time.sleep(5)
    except ConnectionRefusedError as cre:
        logger.warning("Connection Refused! Probably server is not online..: ", cre)
        stream = False
        time.sleep(5)
    except ConnectionAbortedError as cae:
        logger.warning("Connection closed by Client!: ", cae)
        stream = False
        time.sleep(5)
    except ConnectionResetError as cse:
        logger.warning("Connection closed by server!: ", cse)
        stream = False
        time.sleep(5)
    except:
        error_handling()
        stream = False
        time.sleep(5)


class MyRequestsClass:
    def __init__(self, request_type=None, **kwargs):
        self.result = None
        self.status_code = 0
        self.kwargs = kwargs
        self.type = request_type
        self.error = None
        self.run()

    def run(self):
        try:
            if "post" == self.type:
                result = requests.post(**self.kwargs, timeout=180)
            if "get" == self.type:
                result = requests.get(**self.kwargs, timeout=30)
            self.status_code = result.status_code
            self.result = result
            self.error = result.text
        except:
            self.error = sys.exc_info()
            # logger.error("", exc_info=True)


def capture():
    try:
        logger.info("Trying to open camera")
        oldTime = time.time()
        cap = cv2.VideoCapture(0)
        recorded_files = "recorded"
        if not os.path.isdir(recorded_files):
            os.mkdir(recorded_files)
        else:
            for old_file in glob.glob(recorded_files + "/*.mp4"):
                if os.path.getsize(old_file) / 1024 > 100:
                    shutil.move(old_file, files_folder)
                else:
                    os.remove(old_file)

        frame_width, frame_height = (640, 480)
        set_fps = 24
        video_type = "mp4"
        fourcc = "avc1"

        cap.set(3, frame_width)
        cap.set(4, frame_height)

        logger.info(f"Camera Opening Time: {round(time.time() - oldTime, 2)} seconds")

        global save_picture
        global filename
        global picture_folder
        global threadKill
        global frame_count
        global stream
        global pass_the_id

        video_save = False
        streaming_width = 640
        # constant_fps = 1

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        color = (255, 0, 0)

        date_org = (streaming_width - 150, 20)
        time_org = (streaming_width - 130, 45)

        while True:
            ret, img = cap.read()
            if not ret:
                try:
                    camera_is = subprocess.call(["ls", "/dev/video0"])
                    restart_system("warning", f"ret was {ret}: {camera_is}")
                except:
                    restart_system("error", "Camera not Found!")

            if stream:
                try:
                    date = datetime.datetime.now().strftime("%Y/%m/%d")
                    time_now = datetime.datetime.now().strftime("%H:%M:%S")

                    frame = imutils.resize(img, width=streaming_width)

                    frame = cv2.putText(frame, str(date), date_org, font,
                                        font_scale, color, thickness, cv2.LINE_AA)
                    frame = cv2.putText(frame, str(time_now), time_org, font,
                                        font_scale, color, thickness, cv2.LINE_AA)

                    encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    bosluk = b"$"
                    message = bosluk + base64.b64encode(buffer) + bosluk
                    server.sendall(message)
                except:
                    error_handling()
                    stream = False

            if save_picture:
                if not video_save:
                    video_file_path = f'{recorded_files}/{filename}.{video_type}'
                    video_save = True
                    out = cv2.VideoWriter(video_file_path,
                                          cv2.VideoWriter_fourcc(*fourcc), set_fps, (frame_width, frame_height))
                    logger.info(f'Recording Video...')
                    start_of_video_record = time.time()
                    frame_count = 0

                # if int(frame_count / time.time() - start_of_video_record) > 24:
                #     constant_fps += 1
                # elif int(frame_count / time.time() - start_of_video_record) < 24:
                #     constant_fps -= 1
                out.write(img)
                frame_count = frame_count + 1
                if frame_count >= 1440:
                    logger.warning(f"Frame count is too high! {frame_count} frames. Ending the record...")
                    pass_the_id = id_number
                    save_picture = False

            if not save_picture:
                if video_save:
                    video_save = False
                    out.release()

                    if os.path.isfile(video_file_path):
                        video_record_time = round(time.time() - start_of_video_record, 2)
                        file_size = round(os.path.getsize(video_file_path) / (1024 * 1024), 2)
                        if file_size < (1/1024):
                            logger.warning(f"Recorded file size is too small! File size: {file_size} MB")
                            os.remove(video_file_path)
                        else:
                            logger.info(f"Recorded video FileSize={file_size} MB in {video_record_time} seconds and Total {frame_count} frames: {filename}")
                            shutil.move(video_file_path, files_folder)

                    else:
                        logger.warning(f"Opencv couldn't find the file: {video_file_path}")

            if threadKill:
                threadKill = False
                cap.release()
                logger.info("Camera closed.")
                break

            cv2.waitKey(30)

    except:
        error_handling()


def check_running_threads():
    global running_threads_check_time
    threads = [thread.name for thread in threading.enumerate()]
    if time.time() - running_threads_check_time > 30:
        running_threads_check_time = time.time()
        logger.info(f"Running Threads: {threads}")
    return threads


def check_internet():
    global connection
    global url_check
    global pTimeConnection
    global check_connection
    global pTimeCheck
    global garbageLocations
    global values
    global device_type
    global device_information

    timeout_to_download = 20

    while True:
        try:
            if time.time() - pTimeConnection > 3600:
                pTimeConnection = time.time()
                code_date = datetime.datetime.fromtimestamp(os.path.getmtime(destination))
                logger.info(f"Running Code is up to date: {code_date}")

            if time.time() - check_connection > 60:
                check_connection = time.time()
                logger.info("Checking for internet...")

            # log_size = os.path.getsize(log_file_name) / (1024 * 1024)
            if os.path.getsize(log_file_name) / (1024 * 1024) > 1:
                log_file_upload = f"{files_folder}/{get_date()}{hostname}.log"
                logger.info(f"Trying to copy {log_file_upload}...")
                shutil.copy(log_file_name, log_file_upload)
                with open(log_file_name, 'r+') as file:
                    file.truncate()
                logger.info(f"{log_file_upload} copied to {files_folder} folder.")

            requests.get(url_check, timeout=timeout_to_download)

            connection = True

            if connection:
                if "check_folder" not in check_running_threads():
                    logger.info("Checking folder...")
                    threading.Thread(target=check_folder, name="check_folder", daemon=True).start()
                if "listen_to_server" not in check_running_threads():
                    logger.info("Streaming Thread is starting...")
                    threading.Thread(target=listen_to_server, name="listen_to_server", daemon=True).start()
                if time.time() - pTimeCheck > 7200:
                    pTimeCheck = time.time() - 7080

                    logger.info("Checking for updates...")

                    device_information = requests.get(device_informations, timeout=timeout_to_download).json()[hostname]
                    with open("config.json", "w") as config:
                        json.dump(device_information, config)
                    device_type = device_information["device_type"]
                    code = requests.get(url_of_project + device_information["program"], timeout=timeout_to_download)
                    if code.status_code == 200:
                        with open(downloaded, "w") as downloaded_file:
                            downloaded_file.write(code.text)

                        if hash_check(destination) != hash_check(downloaded):
                            logger.info("New update found! Changing the code...")
                            shutil.move(downloaded, destination)
                            logger.info("Code change completed.")
                            restart_system("info", "Updating the code...")
                        else:
                            logger.info("No update found!")

                    else:
                        logger.warning(f"Github Error: {code.status_code}")

                    values = requests.get(url_upload + hostname, timeout=timeout_to_download).json()

                    with open('values.txt', 'w') as jsonfile:
                        json.dump(values, jsonfile)
                    garbageLocations = values['garbageLocations']

                    logger.info("Values saved to Local.")
                    logger.info(f'Count of Garbage Locations: {len(garbageLocations)}')

                    log_size = os.path.getsize(log_file_name) / (1024 * 1024)
                    if log_size > 1:
                        # log_date = datetime.datetime.now().strftime("%Y-%m-%d")
                        # log_time = datetime.datetime.now().strftime("%H-%M-%S")
                        log_file_upload = f"{files_folder}/{get_date()}{hostname}.log"
                        logger.info(f"Trying to copy {log_file_upload}...")
                        shutil.copy(log_file_name, log_file_upload)
                        # rclone_log = subprocess.check_call(
                        #     ["rclone", "move", log_file_upload,
                        #      f"gdrive:Python/ContainerFiles/logs/"])
                        # if not os.path.isfile(log_file_upload):
                        with open(log_file_name, 'r+') as file:
                            file.truncate()
                        logger.info(f"{log_file_upload} copied to {files_folder} folder.")
                        # if os.path.isfile(log_file_upload):
                        #     logger.warning(f"{log_file_upload} log file couldn't uploaded! Rclone Status: {rclone_log}")
                        #     os.remove(log_file_upload)

                    pTimeCheck = time.time()

        except requests.exceptions.ConnectionError:
            if connection:
                connection = False
            logger.info("There is no Internet!")
        except requests.exceptions.ReadTimeout as timeout_error:
            if connection:
                connection = False
            logger.warning(f"Download timeout in {timeout_to_download} seconds: {timeout_error}")
        except:
            error_handling()
            if connection:
                connection = False
                logger.info("There is no connection!")

        time.sleep(20)


downloaded = "downloaded_file.py"
url_of_project = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/"
device_informations = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/device_informations.json"
destination = os.path.basename(__file__)
data_type = str
reader = pynmea2.NMEAStreamReader()
pTimeUpload = 0
pTimeGPS = 0
saveLocationTime = 0
pTimeLog = 0
pTimeConnection = 0
checkCurrentTime = 0
pTimeCheck = 0
take_picture = False
url_location = "https://api2.atiknakit.com/uploadGarbageDeviceLocations/"
url_image = "https://api2.atiknakit.com/uploadGarbageDeviceImage/"
url_check = "https://cdn.atiknakit.com/"
url_upload = "https://api2.atiknakit.com/garbagedevice/"
url_harddrive = "https://cdn.atiknakit.com/upload?"
timeout = 10
connection = False
check_connection = 0
running_threads_check_time = 0
santiye_location = [41.09892610381052, 28.780632617146328]

files_folder = "files"
detectLocationDistance = 61
threadKill = False
filename = None
save_picture = False
id_number = None
pass_the_id = None
stream = False
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
frame_count = 0
server_msg = "wait"
old_location_gps = [0, 0]
on_the_move = False

if not os.path.isdir(files_folder):
    logger.info(f"Making {files_folder} folder")
    os.mkdir(files_folder)

try:
    device_information = requests.get(device_informations, timeout=20).json()[hostname]
    device_type = device_information["device_type"]
    gps_port = device_information["gps_port"]
    with open("config.json", "w") as config:
        json.dump(device_information, config)
    logger.debug("Device Information taken from internet.")
except:
    device_information = json.loads(open('config.json', 'r').read())
    device_type = device_information["device_type"]
    gps_port = device_information["gps_port"]
    logger.debug("Device Information taken from local")

try:
    values = requests.get(url_upload + hostname, timeout=20).json()
    with open('values.txt', 'w') as jsonfile:
        json.dump(values, jsonfile)
    garbageLocations = values['garbageLocations']
    logger.info("Values are taken from internet.")

except:
    values = json.loads(open('values.txt', 'r').read())
    garbageLocations = values['garbageLocations']
    logger.info("Values are taken from local.")

logger.info(f"Hostname: {hostname}\tDevice Type: {device_type}\tGPS Port: {gps_port}")

threading.Thread(target=check_internet, name="check_internet", daemon=True).start()

while True:
    try:
        with serial.Serial(port=gps_port, baudrate=9600, bytesize=8, timeout=1,
                           stopbits=serial.STOPBITS_ONE) as gps_data:
            parse_error_count = 0
            while data_type != 'RMC':
                try:
                    new_data = gps_data.readline().decode('utf-8', errors='replace')
                    if len(new_data) < 1:
                        raise ValueError("Incoming GPS Data is empty")
                    for msg in reader.next(new_data):
                        parsed_data = pynmea2.parse(str(msg))
                        data_type = parsed_data.sentence_type
                except pynmea2.nmea.ParseError as parse_error:
                    parse_error_count = parse_error_count + 1
                    if parse_error_count >= 10:
                        logger.warning(f"Parse Error happened {parse_error_count} times!")
                        time.sleep(1)
                        break
                    continue
                except ValueError as verr:
                    logger.warning(f"{verr}")
                    time.sleep(5)
                    break
                except:
                    error_handling()
                    time.sleep(5)
                    break

        if data_type == "RMC":
            data_type = str

            if parsed_data.status == 'A':
                location_gps = [parsed_data.latitude, parsed_data.longitude]
                time_gps = str(parsed_data.timestamp)
                date_gps = str(parsed_data.datestamp)
                speed_in_kmh = round(parsed_data.spd_over_grnd * 1.852, 3)
                date_local = datetime.datetime.strptime(f"{date_gps} {time_gps[:8]}",
                                                        '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=3)
                logger.info(f'Datetime of GPS: {date_gps} {time_gps} and Speed: {round(speed_in_kmh, 2)} km/s')

                if time.time() - checkCurrentTime > 600:
                    checkCurrentTime = time.time()
                    if abs(datetime.datetime.now() - date_local) > datetime.timedelta(seconds=3):
                        subprocess.call(['sudo', 'date', '-s', date_local.strftime('%Y/%m/%d %H:%M:%S')])
                        logger.info("System Date Updated.")

                if time.time() - saveLocationTime > 5:
                    saveLocationTime = time.time()

                    if geopy.distance.distance(location_gps, old_location_gps).meters > 20:
                        on_the_move = True
                        location_data = {"date": date_local.strftime("%Y-%m-%d %H:%M:%S"), "lat": location_gps[0],
                                         "lng": location_gps[1], "speed": speed_in_kmh}
                        old_location_gps = location_gps
                        if connection:
                            threading.Thread(target=upload_data, name="location_upload",
                                             kwargs={"file_type": "location", "file_data": location_data},
                                             daemon=True).start()
                        else:
                            logger.info("There is no connection. Saving location to file...")
                            write_json(location_data, "locations.json")
                    else:
                        on_the_move = False

                if save_picture:
                    distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                    if distance > detectLocationDistance:
                        save_picture = False
                        logger.info(f'Garbage is out of reach. Distance is: {round(distance, 2)}')
                    else:
                        logger.info(f'Distance: {round(distance, 2)} meters')

                if not save_picture:
                    distances = []
                    pTimeCheckLocations = time.time()
                    for garbageLocation in garbageLocations:
                        distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                        distances.append(distance)
                        if distance < detectLocationDistance and speed_in_kmh > 5:
                            id_number = garbageLocation[2]
                            if id_number == pass_the_id:
                                continue
                            pass_the_id = 0
                            frame_count = 0
                            logger.info(f'Found a close garbage. Distance is: {round(distance, 2)} meters')
                            # logger.info(f'Distance Detection Interval: {detectLocationDistance}')
                            video_date = date_local.strftime('%Y-%m-%d__%H-%M-%S,,')
                            filename = f'{video_date}{location_gps[0]},{location_gps[1]},{id_number}'
                            save_picture = True
                            break

                    minDistance = min(distances)

                    if on_the_move:
                        logger.info(
                            f'Total location check time {round(time.time() - pTimeCheckLocations, 2)} seconds'
                            f' and Minimum distance = {round(minDistance, 2)} meters')
                    if not on_the_move:
                        if geopy.distance.distance(location_gps, santiye_location).meters < 200:
                            logger.info(f"Vehicle is in the station.")
                            time.sleep(30)
                        else:
                            logger.info(f"The vehicle is steady. Location: {location_gps}")
                            if minDistance > 100:
                                time.sleep(minDistance / 20)

                if minDistance >= 100 and not stream:
                    if "opencv" in check_running_threads():
                        logger.info("Closing camera...")
                        threadKill = True

                elif minDistance < 100:
                    if "opencv" not in check_running_threads():
                        logger.info("Starting OpenCV")
                        threading.Thread(target=capture, name="opencv", daemon=True).start()

            elif parsed_data.status == 'V':
                logger.warning(f'Invalid GPS info!!: {parsed_data.status}')
                time.sleep(5)

    except:
        error_handling()
        time.sleep(5)
