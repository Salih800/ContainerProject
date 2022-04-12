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
    import time

    import geopy.distance
    import pynmea2
    import requests
    import serial

    import base64
    import socket
    import imutils
    import subprocess
except ModuleNotFoundError as module:
    print("Module not found: ", module.name, "\tTrying to install it...")
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


def write_json(json_data, json_file_name='locations.json'):
    if not os.path.isfile(f"{files_folder}/{json_file_name}"):
        with open(f"{files_folder}/{json_file_name}", "w"):
            pass

    json_data = json.dumps(json_data)
    with open(f"{files_folder}/{json_file_name}", 'r+') as file:
        data = file.read()
        if len(data) < 1:
            data = f"[{json_data}]"
        else:
            file.seek(len(data)-1)
            data = f",{json_data}]"
        file.write(data)


def upload_data(file_type, file_path=None, file_data=None):
    global uploaded_folder
    try:
        if file_type == "image":
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as img:
                files = {'file': (file_name, img, 'multipart/form-data', {'Expires': '0'})}

                result = requests.post(url_harddrive, files=files)
                status_code = result.status_code
                status = result.json()["status"]

            if status_code == 200 and status == "success":
                uploaded_file = result.json()["filename"]
                logging.info(f"Image File uploaded: {file_name}\tUploaded File: {uploaded_file}")
                # os.remove(file_path)
                shutil.move(file_path, uploaded_folder)
                file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                file_data = {"file_name": uploaded_file, "date": f"{file_date}", "lat": file_lat, "lng": file_lng, "id": file_id}

                try:
                    result = requests.post(url_image + hostname, json=file_data)
                    if not result.status_code == 200:
                        logging.warning(f"Image Name couldn't uploaded! Status Code: {result.status_code}")
                        write_json(file_data, "uploaded_images.json")
                except:
                    error_handling()
                    logging.warning(f"Image Name couldn't uploaded! Saving to file...")
                    write_json(file_data, "uploaded_images.json")

            else:
                logging.error(f"Image file couldn't uploaded! Status Code: {result.status_code}\tStatus: {result.json()}")

        elif file_type == "location":
            try:
                result = requests.post(url_location + hostname, json=file_data)
                if not result.status_code == 200:
                    logging.warning(f"location couldn't uploaded! Status Code: {result.status_code}")
                    write_json(file_data, "locations.json")
            except:
                error_handling()

                logging.warning(f"Location couldn't uploaded! Saving to file...")
                write_json(file_data, "locations.json")

        elif file_type == "locations":
            with open(file_path) as file:
                location_json = json.load(file)
            result = requests.post(url_location + hostname, json=location_json)
            if result.status_code == 200:
                logging.info("locations.json uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"locations.json upload warning: {result.status_code}")

        elif file_type == "uploaded_images":
            with open(file_path) as file:
                videos_json = json.load(file)
            result = requests.post(url_image + hostname, json=videos_json)

            if result.status_code == 200:
                logging.info("uploaded_images.json uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"uploaded_images.json upload warning: {result.status_code}")

    except:
        error_handling()


def check_folder():
    try:
        if connection:
            files_list = os.listdir(files_folder)
            for file in files_list:
                logging.info(f"Files in folder: {len(files_list)}")
                if os.path.isfile(f"{files_folder}/uploaded_images.json"):
                    upload_data(file_type="uploaded_images", file_path=f"{files_folder}/uploaded_images.json")
                if os.path.isfile(f"{files_folder}/locations.json"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.json")
                if file.endswith(".jpg"):
                    upload_data(file_type="image", file_path=f"{files_folder}/{file}")
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
                            threading.Thread(target=capture, name="opencv", args=("stream",), daemon=True).start()

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


def capture(camera_mode):
    try:
        recorded_files = "recorded"
        image_type = "jpg"
        if not os.path.isdir(recorded_files):
            os.mkdir(recorded_files)

        logging.info(f"Trying to open camera in {camera_mode} mode...")
        old_time = time.time()
        cap = cv2.VideoCapture(0)

        recording_width, recording_height = (1280, 960)
        streaming_width, streaming_height = (640, 480)

        if camera_mode == "stream":
            cap.set(3, streaming_width)
            cap.set(4, streaming_height)
        else:
            cap.set(3, recording_width)
            cap.set(4, recording_height)

        logging.info(f"Camera Opening Time: {round(time.time() - old_time, 2)} seconds")

        global save_picture
        global filename
        global threadKill
        global frame_count
        global stream

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        color = (255, 0, 0)

        date_org = (streaming_width - 150, 20)
        time_org = (streaming_width - 130, 45)

        while True:
            ret, img = cap.read()
            if not ret:
                logging.error(f"ret was {ret}: ", subprocess.check_call(["ls", "/dev/video0"]))
                restart_system()

            if stream:
                try:
                    if cap.get(3) != streaming_width:
                        logging.info("Resizing the camera for streaming...")
                        cap.release()
                        cap = cv2.VideoCapture(0)
                        cap.set(3, streaming_width)
                        cap.set(4, streaming_height)
                        continue

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
                except OSError as err:
                    logging.warning(f"OSError: {err}")
                    stream = False
                except:
                    error_handling()
                    stream = False
            else:
                if cap.get(3) != 1280:
                    logging.info("Resizing the camera for recording...")
                    cap.release()
                    cap = cv2.VideoCapture(0)
                    cap.set(3, recording_width)
                    cap.set(4, recording_height)
                    continue

            if save_picture and frame_count < 400:
                image_file_path = f'{recorded_files}/{filename}.{image_type}'
                save_picture = False
                logging.info(f'Taking picture...')
                cv2.imwrite(image_file_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 50])

                if os.path.isfile(image_file_path):
                    file_size = round(os.path.getsize(image_file_path) / 1024, 2)
                    if file_size < 1:
                        logging.warning(f"File size is too small! File size: {file_size}")
                        os.remove(image_file_path)
                    else:
                        logging.info(f"Saved picture FileSize = {file_size} KB: {image_file_path}")
                        shutil.move(image_file_path, files_folder)
                else:
                    logging.warning(f"Opencv couldn't find the file: {image_file_path}")
                frame_count += 1
            elif frame_count >= 400:
                logging.warning(f"Picture count is high! Passing the frame..: {frame_count}")

            if threadKill:
                threadKill = False
                cap.release()
                logging.info("Camera closed.")
                break

            cv2.waitKey(1)

    except:
        error_handling()


def check_running_threads():
    thread_list_folder = []
    for thread_folder in threading.enumerate():
        thread_list_folder.append(thread_folder.name)
    logging.info(f"Running Threads: {thread_list_folder}")


def internet_on():
    global connection
    global url_check
    # global stream_thread
    try:
        check_running_threads()
        requests.get(url_check)
        if not connection:
            connection = True
        if connection:
            thread_list_folder = []
            for thread_folder in threading.enumerate():
                thread_list_folder.append(thread_folder.name)
            if "check_folder" not in thread_list_folder:
                logging.info("Checking folder...")
                threading.Thread(target=check_folder, name="check_folder", daemon=True).start()
            if "listen_to_server" not in thread_list_folder:
                logging.info("listen_to_server is starting...")
                threading.Thread(target=listen_to_server, name="listen_to_server", daemon=True).start()

            logging.info("Internet Connected")

    except requests.exceptions.ConnectionError:
        if connection:
            connection = False
            logging.info("There is no Internet!")

    except:
        if connection:
            connection = False
            logging.info("There is no connection!")
        error_handling()


logging.info("System started")

time.sleep(3)

downloaded = "downloaded_file.py"
url_of_project = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/ContainerVehicle-Online.py"
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
# picture_folder = "pictures/"
connection = False
check_connection = 0

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

logging.info(f"Hostname: {hostname}\tGPS Port: {gps_port}")

while True:
    try:
        if time.time() - check_connection > 10:
            check_connection = time.time()
            logging.info("Checking Connection...")
            threading.Thread(target=internet_on, name="internet_on", daemon=True).start()

        if time.time() - pTimeConnection > 3600:
            pTimeConnection = time.time()

            code_date = datetime.datetime.fromtimestamp(os.path.getmtime(destination))
            logging.info(f"Running Code is up to date: {code_date}")
    except:
        error_handling()

    if connection:
        try:
            if time.time() - pTimeCheck > 7200:
                pTimeCheck = time.time() - 7020

                log_size = os.path.getsize("project.log") / (1024 * 1024)
                if log_size > 1:
                    log_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    log_time = datetime.datetime.now().strftime("%H-%M-%S")
                    log_file_name = f"{log_date}_{log_time}.log"
                    subprocess.check_call(["rclone", "move", "project.log", f"gdrive:Python/ContainerFiles/{log_date}/{hostname}/logs/{log_file_name}"])
                    logging.info("'project.log' uploaded to gdrive.")
                    with open('project.log', 'r+') as file:
                        file.truncate()

                r = requests.get(url_of_project)
                if r.status_code == 200:
                    with open(downloaded, "w") as downloaded_file:
                        downloaded_file.write(r.text)

                    if hash_check(destination) != hash_check(downloaded):
                        logging.info("New update found! Changing the code...")
                        shutil.move(downloaded, destination)
                        logging.info("Code change completed. Restarting...")
                        # subprocess.call(["python", destination])
                        subprocess.call(["sudo", "reboot"])
                    else:
                        logging.info("No update found!")

                else:
                    logging.warning(f"Github Error: {r.status_code}")

                values = requests.get(url_upload + hostname).json()

                with open('values.txt', 'w') as jsonfile:
                    json.dump(values, jsonfile)
                garbageLocations = values['garbageLocations']

                logging.info("Values saved to Local. Connected to the Internet.")
                logging.info(f'Count of Garbage Locations: {len(garbageLocations)}')
                pTimeCheck = time.time()

        except:
            error_handling()

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
                        logging.warning("There is no connection. Saving location to file...")
                        write_json(location_data, "locations.json")

                if take_picture:
                    distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                    if distance > detectLocationDistance:
                        take_picture = False
                        logging.info(f'Garbage is out of reach. Distance is: {round(distance, 2)}')
                    elif speed_in_kmh >= 5.0:
                        logging.info(f'Distance: {round(distance, 2)} meters')

                if not take_picture:
                    distances = []
                    pTimeCheckLocations = time.time()
                    for garbageLocation in garbageLocations:
                        distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                        distances.append(distance)
                        if distance < detectLocationDistance:
                            picture_count = 0
                            id_number = garbageLocation[2]
                            take_picture = True
                            logging.info(f'Found a close garbage. Distance is: {round(distance, 2)} meters')
                            break
                    minDistance = min(distances)
                    logging.info(
                        f'Total location check time {round(time.time() - pTimeCheckLocations, 2)} seconds and Minimum distance = {round(minDistance, 2)} meters')
                if not save_picture:
                    if take_picture and speed_in_kmh < 5.0:
                        logging.info(
                            f'Distance Detection Interval: {detectLocationDistance}\tDistance: {round(distance, 2)} meters')
                        photo_date = date_local.strftime('%Y-%m-%d__%H-%M-%S,,')
                        filename = f'{photo_date}{location_gps[0]},{location_gps[1]},{id_number}.jpg'

                        save_picture = True
                        # logging.warning(subprocess.call(["ls", "/dev/video0"]))
                        time.sleep(1)
                else:
                    logging.warning(f"save_picture was {save_picture}")
                    save_picture = True
                    logging.warning(subprocess.call(["ls", "/dev/video0"]))

                if minDistance >= 100 and not stream:
                    for thread in threading.enumerate():
                        if thread.name == "opencv":
                            logging.info("Killing OpenCV")
                            threadKill = True

                elif minDistance < 100:
                    thread_list = []
                    for thread in threading.enumerate():
                        thread_list.append(thread.name)
                    if "opencv" not in thread_list:
                        logging.info("Starting OpenCV")
                        threading.Thread(target=capture, name="opencv", args=("record", ), daemon=True).start()

            elif parsed_data.status == 'V':
                logging.warning(f'Invalid GPS info!!: {parsed_data.status}')
                time.sleep(5)

    except serial.serialutil.SerialException as serial_error:
        logging.error(f"{serial_error}\tGPS Port: {gps_port}")
        time.sleep(5)

    except:
        error_handling()
