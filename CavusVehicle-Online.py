import hashlib
import logging
import datetime
import json
import os
import shutil
import threading
import sys

import cv2
import paramiko
import subprocess
import time

import geopy.distance
import pynmea2
import requests
import serial

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


def upload_data(file_type, file_path=None, file_data=None):
    try:
        if file_type == "video":
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as video:
                files = {'file': (file_name, video, 'multipart/form-data', {'Expires': '0'})}

                result = requests.post(url_harddrive, files=files)
                status_code, status = result.status_code, result.json()["status"]

            if status_code == 200 and status == "success":
                uploaded_file = result.json()["filename"]
                logging.info(f"Video File uploaded: {file_name}\tUploaded File: {uploaded_file}")
                os.remove(file_path)
                file_date = file_name.split(",,")[0].split("__")
                file_lat, file_lng, file_id = file_name.strip(".mp4").split(",,")[1].split(",")
                file_data = {"file_name": uploaded_file, "date": f"{file_date[0]} {file_date[1]}", "lat": file_lat, "lng": file_lng, "id": file_id}

                try:
                    result = requests.post(url_image + hostname, json=file_data)
                except Exception:
                    exception_type, exception_object, exception_traceback = sys.exc_info()
                    error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
                    line_number = exception_traceback.tb_lineno
                    logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

                    logging.warning(f"Video Name couldn't uploaded! Saving to file...")
                    with open(f"{files_folder}/uploaded_files.txt", "a") as uploaded_files:
                        uploaded_files.write(f"{file_data}\n")

                if not result.status_code == 200:
                    logging.warning(f"Video Name couldn't uploaded! Status Code: {result.status_code}")
                    with open(f"{files_folder}/uploaded_files.txt","a") as uploaded_files:
                        uploaded_files.write(f"{file_data}\n")

            else:
                logging.error(f"Status Code: {result.status_code}\tStatus: {result.json()}")

        elif file_type == "location":
            try:
                result = requests.post(url_location + hostname, json=file_data)
            except Exception:
                exception_type, exception_object, exception_traceback = sys.exc_info()
                error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
                line_number = exception_traceback.tb_lineno
                logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

                logging.warning(f"Location couldn't uploaded! Saving to file...")
                with open(f"{files_folder}/locations.txt", "a") as locations_file:
                    locations_file.write(f"{file_data}\n")

            if not result.status_code == 200:
                logging.warning(f"location couldn't uploaded! Status Code: {result.status_code}")
                with open(f"{files_folder}/locations.txt","a") as locations_file:
                    locations_file.write(f"{file_data}\n")

        elif file_type == "locations":
            location_json_list = []
            with open(file_path, "r") as location_file:
                locations = location_file.read().split("\n")
            for location in locations:
                location_json_list.append(location)
            result = requests.post(url_location + hostname, json=location_json_list)
            if result.status_code == 200:
                logging.info("locations.txt uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"locations.txt upload warning: {result.status_code}")

        elif file_type == "uploaded_files":
            file_list_json = []
            with open(file_path, "r") as uploaded_file:
                uploaded_files = uploaded_file.read().split("\n")
            for file_json in uploaded_files:
                file_list_json.append(file_json)

            result = requests.post(url_image + hostname, json=file_list_json)

            if result.status_code == 200:
                logging.info("uploaded_files.txt uploaded")
                os.remove(file_path)
            else:
                logging.warning(f"uploaded_files.txt upload warning: {result.status_code}")
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
                if os.path.isfile(f"{files_folder}/uploaded_files.txt"):
                    upload_data(file_type="uploaded_files", file_path=f"{files_folder}/uploaded_files.txt")
                if os.path.isfile(f"{files_folder}/locations.txt"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.txt")
                if file.endswith(".mp4"):
                    upload_data(file_type="video", file_path=f"{files_folder}/{file}")
    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


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

        video_save = False
        frame_count = 0

        while True:
            ret, img = cap.read()
            if not ret:
                logging.error("ret was False")
                break

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
                        logging.info(
                            f"Recorded video FileSize={file_size} MB in {video_record_time} seconds and Total {frame_count} frames: {filename}")
                        if connection:
                            threading.Thread(target=upload_data,
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


def internet_on():
    global connection
    global url_check
    try:
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
            else:
                logging.warning("'check_folder' thread exist in thread_list!")
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
detectLocationDistance = 100
threadKill = False
filename = None
save_picture = False
hostname = "empty"
id_number = None

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
            threading.Thread(target=internet_on, daemon=True).start()

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
                        threading.Thread(target=upload_data, kwargs={"file_type": "location", "file_data": location_data}, daemon=True).start()
                    else:
                        with open(f"{files_folder}/locations.txt", "a") as locations_file:
                            locations_file.write(f"{location_data}\n")

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
                            save_picture = True
                            break

                    minDistance = min(distances)
                    logging.info(
                        f'Total location check time {round(time.time() - pTimeCheckLocations, 2)} seconds and Minimum distance = {round(minDistance, 2)} meters')

                if minDistance >= 200:
                    for thread in threading.enumerate():
                        if thread.name == "opencv":
                            logging.info("Killing OpenCV")
                            threadKill = True

                else:
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
