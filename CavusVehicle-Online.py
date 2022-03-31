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
    try:
        if file_type == "video":
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as video:
                files = {'file': (file_name, video, 'multipart/form-data', {'Expires': '0'})}

                result = requests.post(url_harddrive, files=files)
                status_code = result.status_code
                logging.info(f"result.json(): {result.json()}")
                status = result.json()["status"]

            if status_code == 200 and status == "success":
                uploaded_file = result.json()["filename"]
                logging.info(f"Video File uploaded: {file_name}\tUploaded File: {uploaded_file}")
                os.remove(file_path)
                file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                file_data = {"file_name": uploaded_file, "date": f"{file_date}", "lat": file_lat, "lng": file_lng, "id": file_id}

                try:
                    result = requests.post(url_image + hostname, json=file_data)
                    if not result.status_code == 200:
                        logging.warning(f"Video Name couldn't uploaded! Status Code: {result.status_code}")
                        write_json(file_data, "uploaded_videos.json")
                except Exception:
                    exception_type, exception_object, exception_traceback = sys.exc_info()
                    error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
                    line_number = exception_traceback.tb_lineno
                    logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

                    logging.warning(f"Video Name couldn't uploaded! Saving to file...")
                    write_json(file_data, "uploaded_videos.json")

            else:
                logging.error(f"Video file couldn't uploaded! Status Code: {result.status_code}\tStatus: {result.json()}")

        elif file_type == "location":
            try:
                result = requests.post(url_location + hostname, json=file_data)
                if not result.status_code == 200:
                    logging.warning(f"location couldn't uploaded! Status Code: {result.status_code}")
                    write_json(file_data, "locations.json")
            except Exception:
                exception_type, exception_object, exception_traceback = sys.exc_info()
                error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
                line_number = exception_traceback.tb_lineno
                logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

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

        elif file_type == "uploaded_videos":
            with open(file_path) as file:
                videos_json = json.load(file)
            result = requests.post(url_image + hostname, json=videos_json)

            if result.status_code == 200:
                logging.info("uploaded_videos.json uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"uploaded_videos.json upload warning: {result.status_code}")

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


def check_folder():
    try:
        if connection:
            files_list = os.listdir(files_folder)
            for file in files_list:
                logging.info(f"Files in folder: {len(files_list)}")
                if os.path.isfile(f"{files_folder}/uploaded_videos.json"):
                    upload_data(file_type="uploaded_videos", file_path=f"{files_folder}/uploaded_videos.json")
                if os.path.isfile(f"{files_folder}/locations.json"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.json")
                if file.endswith(".mp4"):
                    upload_data(file_type="video", file_path=f"{files_folder}/{file}")
    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


def stream_to_server():
    global stream, hostname, server
    host = "93.113.96.30"
    port = 8181
    BUFF_SIZE = 65536

    try:
        logging.info("Trying to connect to Streaming Server")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.connect((host, port))
        id_message = bytes("$" + hostname + "$", "utf-8")
        server.sendall(id_message)
        logging.info("Message sent to the Server")

        while True:
            server_msg = server.recv(BUFF_SIZE)
            if server_msg == b"$start$":
                stream = True
                logging.info("Start stream komutu verildi")
                thread_list_folder = []
                for thread_folder in threading.enumerate():
                    thread_list_folder.append(thread_folder.name)
                if "opencv" not in thread_list_folder:
                    logging.info("Starting OpenCV")
                    threading.Thread(target=capture, name="opencv", daemon=True).start()

            elif server_msg == b"$stop$":
                stream = False
                print("Stop stream komutu verildi")

            else:
                logging.warning(f"Unknown message from server: {server_msg}")
                time.sleep(30)

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(
            f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")
        time.sleep(5)


def capture():
    try:
        logging.info("Trying to open camera")
        oldTime = time.time()
        cap = cv2.VideoCapture(0)

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

        video_save = False
        streaming_width = 640

        while True:
            ret, img = cap.read()
            if not ret:
                logging.error(f"ret was {ret}. Restarting the code")
                subprocess.call(["python", destination])
                sys.exit("Shutting down")

            if stream:
                try:
                    frame = imutils.resize(img, width=streaming_width)
                    encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    bosluk = b"$"
                    message = bosluk + base64.b64encode(buffer) + bosluk
                    server.sendall(message)
                except Exception:
                    exception_type, exception_object, exception_traceback = sys.exc_info()
                    error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
                    line_number = exception_traceback.tb_lineno
                    logging.error(
                        f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

            if save_picture:
                if not video_save:
                    video_save = True
                    out = cv2.VideoWriter(f'{files_folder}/{filename}.{video_type}',
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

                    if os.path.isfile(f'{files_folder}/{filename}.{video_type}'):
                        video_record_time = round(time.time() - start_of_video_record, 2)
                        file_size = round(os.path.getsize(f'{files_folder}/{filename}.{video_type}') / (1024 * 1024), 2)
                        if file_size < (1/1024):
                            logging.warning(f"Recorded file size is too small! File size: {file_size} MB")
                            os.remove(f'{picture_folder}{filename}.{video_type}')
                        else:
                            logging.info(f"Recorded video FileSize={file_size} MB in {video_record_time} seconds and Total {frame_count} frames: {filename}")

                        if connection:
                            threading.Thread(target=upload_data, name="video_upload",
                                             kwargs={"file_type": "video", "file_path": f'{files_folder}/{filename}.{video_type}'},
                                             daemon=True).start()
                    else:
                        logging.warning(f"Opencv couldn't find the file: {filename}")

            if threadKill:
                threadKill = False
                break

            cv2.waitKey(1)

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(
            f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


def check_running_threads():
    thread_list_folder = []
    for thread_folder in threading.enumerate():
        thread_list_folder.append(thread_folder.name)
    logging.info(f"Running Threads: {thread_list_folder}")


def internet_on():
    global connection
    global url_check
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
            # if "opencv" not in thread_list_folder:
            #     logging.info("Starting OpenCV")
            #     threading.Thread(target=capture, name="opencv", daemon=True).start()
            if "stream_to_server" not in thread_list_folder:
                logging.info("Streaming Thread is starting...")
                threading.Thread(target=stream_to_server, name="stream_to_server", daemon=True).start()

            logging.info("Internet Connected")

    except requests.exceptions.ConnectionError:
        if connection:
            connection = False
            logging.info("Connection Closed!")

    except Exception:
        if connection:
            connection = False
            logging.info("There is no connection!")
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(
            f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


logging.info("System started")

time.sleep(3)

downloaded = "downloaded_file.py"
url_of_project = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/CavusVehicle-Online.py"
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

files_folder = "files"
detectLocationDistance = 61
threadKill = False
filename = None
save_picture = False
hostname = "empty"
id_number = None
stream = False
server = None
frame_count = 0

try:
    subprocess.check_call(["ls", "/dev/ttyACM0"])
    gps_port = "/dev/ttyACM0"

except Exception as e:
    gps_port = "/dev/ttyS0"

try:
    hostname = subprocess.check_output(["hostname"]).decode("utf-8").strip("\n")

    if not os.path.isdir(files_folder):
        logging.info(f"Making {files_folder} folder")
        os.mkdir(files_folder)

    logging.info("Getting values from local...")
    values = json.loads(open('values.txt', 'r').read())
    garbageLocations = values['garbageLocations']

except Exception:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
    line_number = exception_traceback.tb_lineno
    logging.error(
        f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

logging.info(f"Hostname: {hostname}\tPort: {gps_port}")


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
    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

    if connection:
        try:
            if time.time() - pTimeCheck > 7200:
                pTimeCheck = time.time()

                r = requests.get(url_of_project)
                if r.status_code == 200:
                    with open(downloaded, "w") as downloaded_file:
                        downloaded_file.write(r.text)

                    if hash_check(destination) != hash_check(downloaded):
                        logging.info("New update found! Changing the code...")
                        shutil.move(downloaded, destination)
                        logging.info("Code change completed. Restarting...")
                        subprocess.call(["python", destination])
                        sys.exit("Shutting down")
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

        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
            line_number = exception_traceback.tb_lineno
            logging.error(
                f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

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
                        logging.warning(f"Parse Error happened {parse_error_count} times: {parse_error}")
                    continue
                except ValueError as verr:
                    logging.warning(f"{verr}")
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
                logging.info(f'Datetime of GPS: {date_gps} {time_gps} and Speed: {round(speed_in_kmh, 2)} km/s')

                if time.time() - checkCurrentTime > 600:
                    if abs(datetime.datetime.now() - date_local) > datetime.timedelta(seconds=3):
                        subprocess.call(['sudo', 'date', '-s', date_local.strftime('%Y/%m/%d %H:%M:%S')])
                        logging.info("System Date Updated.")

                if time.time() - saveLocationTime > 5:
                    saveLocationTime = time.time()
                    # location_data = f'{date_local};{location_gps[0]},{location_gps[1]};{round(speed_in_kmh, 3)}'
                    location_data = {"date": date_local.strftime("%Y-%m-%d %H:%M:%S"), "lat": location_gps[0], "lng": location_gps[1], "speed": speed_in_kmh}
                    if connection:
                        threading.Thread(target=upload_data, name="location_upload", kwargs={"file_type": "location", "file_data": location_data}, daemon=True).start()
                    else:
                        logging.warning("There is no connection. Saving location to file...")
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
                    logging.info(
                        f'Total location check time {round(time.time() - pTimeCheckLocations, 2)} seconds and Minimum distance = {round(minDistance, 2)} meters')

                if minDistance >= 100:
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
                        threading.Thread(target=capture, name="opencv", daemon=True).start()

            elif parsed_data.status == 'V':
                logging.warning(f'Invalid GPS info!!: {parsed_data.status}')
                time.sleep(5)

    except serial.serialutil.SerialException as serial_error:
        logging.error(f"{serial_error}\tPort: {gps_port}")
        time.sleep(5)

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(
            f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")
