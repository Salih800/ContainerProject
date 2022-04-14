try:
    import hashlib
    import logging
    import datetime
    import json
    import os
    import shutil
    import threading
    import sys

    import cv2
    import subprocess
    import time

    import geopy.distance
    import pynmea2
    import requests
    import serial

    import base64
    import socket
    import imutils
except ModuleNotFoundError as module:
    print("Module not found: ", module.name, "\tTrying to install ", module.name)
    import subprocess
    subprocess.check_call(["pip", "install", module.name])
    subprocess.call(["sudo", "reboot"])
# hello_21-12-2021

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO, filename='project.log',
    datefmt='%Y-%m-%d %H:%M:%S')

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.WARNING, filename='project.log',
    datefmt='%Y-%m-%d %H:%M:%S')

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.ERROR, filename='project.log',
    datefmt='%Y-%m-%d %H:%M:%S')


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
    logging.error(f"Type: {exception_type}\tObject: {exception_object}\tLine number: {line_number}")


def restart_system():
    logging.info("Restarting the system")
    subprocess.call(["sudo", "reboot"])
    sys.exit("Rebooting...")


def write_json(json_data, json_file_name='locations.json'):
    json_file_path = f"{files_folder}/{json_file_name}"
    if not os.path.isfile(json_file_path):
        with open(json_file_path, "w"):
            pass

    json_data = json.dumps(json_data)
    with open(json_file_path, 'r+') as json_file:
        data = json_file.read()
        if len(data) < 1:
            data = f"[{json_data}]"
        else:
            json_file.seek(len(data)-1)
            data = f",{json_data}]"
        json_file.write(data)


def upload_data(file_type, file_path=None, file_data=None):
    global uploaded_folder
    timeout_to_upload = 60
    try:
        if file_type == "video":
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as video:
                files = {'file': (file_name, video, 'multipart/form-data', {'Expires': '0'})}

                result = requests.post(url_harddrive, files=files, timeout=timeout_to_upload)
                status_code = result.status_code
                # logging.info(f"result.json(): {result.json()}")
                status = result.json()["status"]

            if status_code == 200 and status == "success":
                uploaded_file = result.json()["filename"]
                logging.info(f"Video File uploaded: {file_name}")
                write_json({"file_name": file_name, "uploaded_file": uploaded_file}, "uploaded_files.json")
                # shutil.move(file_path, uploaded_folder)
                file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                file_data = {"file_name": uploaded_file, "date": f"{file_date}", "lat": file_lat, "lng": file_lng, "id": file_id}

                try:
                    result = requests.post(url_image + hostname, json=file_data, timeout=timeout_to_upload)
                    if not result.status_code == 200:
                        logging.warning(f"Video Name couldn't uploaded! Status Code: {result.status_code}")
                        write_json(file_data, "uploaded_videos.json")
                except:
                    error_handling()
                    logging.warning(f"Video Name couldn't uploaded! Saving to file...")
                    write_json(file_data, "uploaded_videos.json")

                os.remove(file_path)

            else:
                logging.error(f"Video file couldn't uploaded! Status Code: {result.status_code}\tStatus: {result.json()}")

        elif file_type == "location":
            try:
                result = requests.post(url_location + hostname, json=file_data, timeout=timeout_to_upload)
                if not result.status_code == 200:
                    logging.warning(f"location couldn't uploaded! Status Code: {result.status_code}")
                    write_json(file_data, "locations.json")
            except requests.exceptions.ConnectionError:
                logging.warning(f"No internet. Location couldn't uploaded! Saving to file...")
                write_json(file_data, "locations.json")
            except requests.exceptions.ReadTimeout:
                logging.warning(f"Connection timeout in {timeout_to_upload} seconds: {url_location}")
                write_json(file_data, "locations.json")
            except:
                error_handling()
                logging.warning(f"Location couldn't uploaded! Saving to file...")
                write_json(file_data, "locations.json")

        elif file_type == "locations":
            with open(file_path) as file:
                location_json = json.load(file)
            result = requests.post(url_location + hostname, json=location_json, timeout=timeout_to_upload)
            if result.status_code == 200:
                logging.info("locations.json uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"locations.json upload warning: {result.status_code}")

        elif file_type == "uploaded_videos":
            with open(file_path) as file:
                videos_json = json.load(file)
            result = requests.post(url_image + hostname, json=videos_json, timeout=timeout_to_upload)
            if result.status_code == 200:
                logging.info("uploaded_videos.json uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"uploaded_videos.json upload warning: {result.status_code}")
        elif file_type == "uploaded_files":
            if os.path.getsize(file_path) / 1024 > 500:
                uploaded_files_date = datetime.datetime.now().strftime("%Y-%m-%d")
                uploaded_files_time = datetime.datetime.now().strftime("%H-%M-%S")
                uploaded_files_name = f"{uploaded_files_date}_{uploaded_files_time}_{hostname}.json"
                shutil.move(file_path, uploaded_files_name)
                subprocess.check_call(
                    ["rclone", "move", uploaded_files_name, f"gdrive:Python/ContainerFiles/{uploaded_files_date}/{hostname}/pictures/"])
                logging.info("'uploaded_files.json' uploaded to gdrive.")

    except:
        error_handling()


def get_folder_size(path_to_folder):
    size = 0
    for path, dirs, files in os.walk(path_to_folder):
        for f in files:
            fp = os.path.join(path, f)
            size += os.path.getsize(fp)
    return size


def file_size_unit(size: int) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if size < 1024:
            break
        size /= 1024
    return f"{size:.1f}{unit}"


def check_folder():
    try:
        upload_start_time = time.time()
        files_list = os.listdir(files_folder)
        upload_start_size = get_folder_size(files_folder)
        if len(files_list) > 1:
            logging.info(f"Files in folder: {len(files_list)}")
        for file_to_upload in files_list:
            if connection:
                if os.path.isfile(f"{files_folder}/uploaded_files.json"):
                    upload_data(file_type="uploaded_files", file_path=f"{files_folder}/uploaded_files.json")
                if os.path.isfile(f"{files_folder}/uploaded_videos.json"):
                    upload_data(file_type="uploaded_videos", file_path=f"{files_folder}/uploaded_videos.json")
                if os.path.isfile(f"{files_folder}/locations.json"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.json")
                if file_to_upload.endswith(".mp4"):
                    upload_data(file_type="video", file_path=f"{files_folder}/{file_to_upload}")
        total_uploaded_file = len(files_list) - os.listdir(files_folder)
        if len(files_list) - os.listdir(files_folder) > 0:
            upload_end_size = file_size_unit(get_folder_size(files_folder) - upload_start_size)
            upload_end_time = round(time.time() - upload_start_time, 2)
            logging.info(f"{total_uploaded_file} files and {upload_end_size} uploaded in {upload_end_time} seconds")
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
        logging.info("Trying to connect to Streaming Server")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (host, port)
        server.connect(server_address)
        server.settimeout(60)
        id_message = bytes("$id" + hostname + "$", "utf-8")
        server.sendall(id_message)
        logging.info(f"Id message sent to the Server: {id_message}")
        server.sendall(alive_msg)
        while True:
            logging.info("Listening server...")
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
                        logging.info("Stream started.")
                        thread_list_folder = []
                        for thread_folder in threading.enumerate():
                            thread_list_folder.append(thread_folder.name)
                        if "opencv" not in thread_list_folder:
                            logging.info("Starting OpenCV")
                            threading.Thread(target=capture, name="opencv", daemon=True).start()

                    elif command == "stop":
                        stream = False
                        # threadKill = True
                        logging.info("Stream stopped.")
                    elif command == "k":
                        if not stream:
                            server.sendall(alive_msg)
                        logging.info("Server is Online.")
                    else:
                        logging.warning(f"Unknown message from server: {command}")
                        time.sleep(5)
            else:
                logging.error(f"Empty byte from Server. Closing the connection!: Server Message: {server_msg}")
                server.close()
                break

    except socket.timeout:
        logging.warning("Server timeout in 60 seconds! Closing the connection.")
        stream = False
        time.sleep(5)
    except ConnectionRefusedError as cre:
        logging.warning("Connection Refused! Probably server is not online..: ", cre)
        stream = False
        time.sleep(5)
    except ConnectionAbortedError as cae:
        logging.warning("Connection closed by Client!: ", cae)
        stream = False
        time.sleep(5)
    except ConnectionResetError as cse:
        logging.warning("Connection closed by server!: ", cse)
        stream = False
        time.sleep(5)
    except:
        error_handling()
        stream = False
        time.sleep(5)


def capture():
    try:
        logging.info("Trying to open camera")
        oldTime = time.time()
        cap = cv2.VideoCapture(0)
        recorded_files = "recorded"
        if not os.path.isdir(recorded_files):
            os.mkdir(recorded_files)

        frame_width, frame_height = (640, 480)
        set_fps = 24
        video_type = "mp4"
        fourcc = "avc1"

        cap.set(3, frame_width)
        cap.set(4, frame_height)

        logging.info(f"Camera Opening Time: {round(time.time() - oldTime, 2)} seconds")

        global save_picture
        global filename
        global picture_folder
        global threadKill
        global frame_count
        global stream

        video_save = False
        streaming_width = 640

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        color = (255, 0, 0)

        date_org = (streaming_width - 150, 20)
        time_org = (streaming_width - 130, 45)

        while True:
            ret, img = cap.read()
            if not ret:
                logging.error(f"ret was {ret}. Restarting the code")
                subprocess.call(["python", destination])
                sys.exit("Shutting down")

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
                except BrokenPipeError as broken_pipe:
                    stream = False
                    logging.error(f"BrokenPipeError! Stream stopping...: {broken_pipe}")
                    time.sleep(5)
                    continue

                except ConnectionResetError:
                    logging.warning("Connection closed. Waiting for connection...")
                    stream = False
                    time.sleep(5)
                    continue

                except:
                    error_handling()
                    stream = False

            if save_picture:
                if not video_save:
                    video_file_path = f'{recorded_files}/{filename}.{video_type}'
                    video_save = True
                    out = cv2.VideoWriter(video_file_path,
                                          cv2.VideoWriter_fourcc(*fourcc), set_fps, (frame_width, frame_height))
                    logging.info(f'Recording Video...')
                    start_of_video_record = time.time()
                    frame_count = 0

                out.write(img)
                frame_count = frame_count + 1
                if frame_count > 2880:
                    logging.warning(f"Frame count is too high! {frame_count} frames. Ending the record...")
                    save_picture = False

            if not save_picture:
                if video_save:
                    video_save = False
                    out.release()

                    if os.path.isfile(video_file_path):
                        video_record_time = round(time.time() - start_of_video_record, 2)
                        file_size = round(os.path.getsize(video_file_path) / (1024 * 1024), 2)
                        if file_size < (1/1024):
                            logging.warning(f"Recorded file size is too small! File size: {file_size} MB")
                            os.remove(video_file_path)
                        else:
                            logging.info(f"Recorded video FileSize={file_size} MB in {video_record_time} seconds and Total {frame_count} frames: {filename}")
                            shutil.move(video_file_path, files_folder)

                    else:
                        logging.warning(f"Opencv couldn't find the file: {video_file_path}")

            if threadKill:
                threadKill = False
                cap.release()
                logging.info("Camera closed.")
                break

            cv2.waitKey(1)

    except:
        error_handling()


def check_running_threads():
    global running_threads_check_time
    threads = [thread.name for thread in threading.enumerate()]
    if time.time() - running_threads_check_time > 30:
        running_threads_check_time = time.time()
        logging.info(f"Running Threads: {threads}")
    return threads


def check_internet():
    global connection
    global url_check
    global pTimeConnection
    global check_connection
    global pTimeCheck
    global garbageLocations
    global values

    timeout_to_download = 20

    while True:
        try:
            if time.time() - pTimeConnection > 3600:
                pTimeConnection = time.time()
                code_date = datetime.datetime.fromtimestamp(os.path.getmtime(destination))
                logging.info(f"Running Code is up to date: {code_date}")

            requests.get(url_check, timeout=timeout_to_download)

            connection = True
            if time.time() - check_connection > 60:
                check_connection = time.time()
                logging.info("Internet Connected.")

            if connection:
                if "check_folder" not in check_running_threads():
                    logging.info("Checking folder...")
                    threading.Thread(target=check_folder, name="check_folder", daemon=True).start()
                if "listen_to_server" not in check_running_threads():
                    logging.info("Streaming Thread is starting...")
                    threading.Thread(target=listen_to_server, name="listen_to_server", daemon=True).start()
                if time.time() - pTimeCheck > 7200:
                    pTimeCheck = time.time() - 7080

                    logging.info("Checking for updates...")

                    device_information = requests.get(device_informations, timeout=timeout_to_download).json()[hostname]
                    code = requests.get(url_of_project + device_information["program"], timeout=timeout_to_download)
                    if code.status_code == 200:
                        with open(downloaded, "w") as downloaded_file:
                            downloaded_file.write(code.text)

                        if hash_check(destination) != hash_check(downloaded):
                            logging.info("New update found! Changing the code...")
                            shutil.move(downloaded, destination)
                            logging.info("Code change completed.")
                            restart_system()
                        else:
                            logging.info("No update found!")

                    else:
                        logging.warning(f"Github Error: {code.status_code}")

                    values = requests.get(url_upload + hostname, timeout=timeout_to_download).json()

                    with open('values.txt', 'w') as jsonfile:
                        json.dump(values, jsonfile)
                    garbageLocations = values['garbageLocations']

                    logging.info("Values saved to Local.")
                    logging.info(f'Count of Garbage Locations: {len(garbageLocations)}')

                    log_size = os.path.getsize("project.log") / (1024 * 1024)
                    if log_size > 1:
                        log_date = datetime.datetime.now().strftime("%Y-%m-%d")
                        log_time = datetime.datetime.now().strftime("%H-%M-%S")
                        log_file_name = f"{log_date}_{log_time}_{hostname}.log"
                        logging.info(f"Trying to upload {log_file_name}...")
                        shutil.copy("project.log", log_file_name)
                        rclone_log = subprocess.check_call(
                            ["rclone", "move", log_file_name,
                             f"gdrive:Python/ContainerFiles/{log_date}/{hostname}/logs/"])
                        if not os.path.isfile(log_file_name):
                            with open('project.log', 'r+') as file:
                                file.truncate()
                            logging.info(f"{log_file_name} uploaded to gdrive.")
                        if os.path.isfile(log_file_name):
                            logging.warning(f"{log_file_name} log file couldn't uploaded! Rclone Status: {rclone_log}")
                            os.remove(log_file_name)

                    pTimeCheck = time.time()

        except requests.exceptions.ConnectionError:
            if connection:
                connection = False
                logging.info("There is no Internet!")
        except requests.exceptions.ReadTimeout as timeout_error:
            if connection:
                connection = False
            logging.warning(f"Connection timeout in {timeout_to_download} seconds: {timeout_error}")

        except:
            if connection:
                connection = False
                logging.info("There is no connection!")
            error_handling()

        time.sleep(20)


logging.info("System started\n\n")

time.sleep(3)

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
url_harddrive = "https://cdn.atiknakit.com/upload?type=garbagedevice"
timeout = 10
picture_folder = "pictures/"
connection = False
check_connection = 0
running_threads_check_time = 0
santiye_location = [41.09892610381052, 28.780632617146328]

files_folder = "files"
detectLocationDistance = 61
threadKill = False
filename = None
save_picture = False
hostname = "empty"
id_number = None
stream = False
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
frame_count = 0
uploaded_folder = "uploaded_files"
server_msg = "wait"
# stream_thread = None

try:
    subprocess.check_call(["ls", "/dev/ttyACM0"])
    gps_port = "/dev/ttyACM0"
except:
    gps_port = "/dev/ttyS0"

try:
    hostname = subprocess.check_output(["hostname"]).decode("utf-8").strip("\n")

    if not os.path.isdir(files_folder):
        logging.info(f"Making {files_folder} folder")
        os.mkdir(files_folder)
    if not os.path.isdir(uploaded_folder):
        logging.info(f"Making {uploaded_folder} folder")
        os.mkdir(uploaded_folder)

    logging.info("Getting values from local...")
    values = json.loads(open('values.txt', 'r').read())
    garbageLocations = values['garbageLocations']

except:
    error_handling()

logging.info(f"Hostname: {hostname}\tPort: {gps_port}")

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
                        logging.warning(f"Parse Error happened {parse_error_count} times!")
                        time.sleep(1)
                        break
                    continue
                except ValueError as verr:
                    logging.warning(f"{verr}")
                    time.sleep(5)
                    break
                except:
                    error_handling()

        if data_type == "RMC":
            data_type = str

            if parsed_data.status == 'A':
                location_gps = [parsed_data.latitude, parsed_data.longitude]
                time_gps = str(parsed_data.timestamp)
                date_gps = str(parsed_data.datestamp)
                speed_in_kmh = round(parsed_data.spd_over_grnd * 1.852, 3)
                date_local = datetime.datetime.strptime(f"{date_gps} {time_gps[:8]}",
                                                        '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=3)
                logging.info(f'Datetime of GPS: {date_gps} {time_gps} and Speed: {round(speed_in_kmh, 2)} km/s')

                if time.time() - checkCurrentTime > 600:
                    checkCurrentTime = time.time()
                    if abs(datetime.datetime.now() - date_local) > datetime.timedelta(seconds=3):
                        subprocess.call(['sudo', 'date', '-s', date_local.strftime('%Y/%m/%d %H:%M:%S')])
                        logging.info("System Date Updated.")

                if time.time() - saveLocationTime > 5:
                    saveLocationTime = time.time()
                    location_data = {"date": date_local.strftime("%Y-%m-%d %H:%M:%S"), "lat": location_gps[0], "lng": location_gps[1], "speed": speed_in_kmh}
                    if connection:
                        threading.Thread(target=upload_data, name="location_upload", kwargs={"file_type": "location", "file_data": location_data}, daemon=True).start()
                    else:
                        logging.info("There is no connection. Saving location to file...")
                        write_json(location_data, "locations.json")

                if save_picture:
                    distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                    if distance > detectLocationDistance:
                        save_picture = False
                        logging.info(f'Garbage is out of reach. Distance is: {round(distance, 2)}')
                    else:
                        logging.info(f'Distance: {round(distance, 2)} meters')

                if not save_picture:
                    distances = []
                    pTimeCheckLocations = time.time()
                    for garbageLocation in garbageLocations:
                        distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                        distances.append(distance)
                        if distance < detectLocationDistance:
                            id_number = garbageLocation[2]
                            logging.info(f'Found a close garbage. Distance is: {round(distance, 2)} meters')
                            logging.info(f'Distance Detection Interval: {detectLocationDistance}')
                            video_date = date_local.strftime('%Y-%m-%d__%H-%M-%S,,')
                            filename = f'{video_date}{location_gps[0]},{location_gps[1]},{id_number}'
                            frame_count = 0
                            save_picture = True
                            break

                    minDistance = min(distances)
                    logging.info(f'Total location check time {round(time.time() - pTimeCheckLocations, 2)} seconds and Minimum distance = {round(minDistance, 2)} meters')
                    if geopy.distance.distance(location_gps, santiye_location).meters < 100:
                        time.sleep(30)

                if minDistance >= 100 and not stream:
                    if "opencv" in check_running_threads():
                        logging.info("Closing camera...")
                        threadKill = True

                elif minDistance < 100:
                    if "opencv" not in check_running_threads():
                        logging.info("Starting OpenCV")
                        threading.Thread(target=capture, name="opencv", daemon=True).start()

            elif parsed_data.status == 'V':
                logging.warning(f'Invalid GPS info!!: {parsed_data.status}')
                time.sleep(5)

    except serial.serialutil.SerialException as serial_error:
        logging.error(f"{serial_error}\tPort: {gps_port}")
        time.sleep(5)

    except:
        error_handling()
