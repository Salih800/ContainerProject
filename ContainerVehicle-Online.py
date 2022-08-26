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
import threading
import time
import math

hostname = socket.gethostname()
requirements = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/requirements.txt"
yolov5_reqs = "https://raw.githubusercontent.com/ultralytics/yolov5/master/requirements.txt"

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
    import pynmea2
    import requests
    import imutils
    import serial
    import cv2
    import torch
    from cv2 import imwrite as my_imwrite
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

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


def restart_system(restart_type=None, why=None):
    if restart_type == "info":
        logger.info(f"Restarting the system: {why}")
    if restart_type == "warning":
        logger.warning(f"Restarting the system: {why}")
    if restart_type == "error":
        logger.error(f"Restarting the system: {why}")
    subprocess.call(["sudo", "reboot"])
    time.sleep(60)


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
        logger.error(f"JSON write error: {json_file_path}", exc_info=True)


def read_json(json_file):
    try:
        data = json.load(open(json_file, "r"))
    except json.decoder.JSONDecodeError as json_error:
        logger.warning(f"JSONDecodeError happened at {json_file}: {json_error.pos}. Trying to save the file...")
        if json_error.pos == 0:
            data = []
        else:
            data = json.loads(open(json_file).read()[:json_error.pos])
        logger.info(f"{len(data)} file info saved.")
    return data


def draw_text_and_rectangle(frame, text, x=0, y=0, font_scale=15, img_color=(255, 255, 255), rect_color=(0, 0, 0)):
    font = ImageFont.load_default()
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)

    w, h = font.getsize(text)
    w, h = w + 1, h + 1

    draw.rectangle((x, y, x + w, y + h), fill=rect_color)

    draw.text((x, y), text, fill=img_color, font=font)

    return np.array(img)


def calculate_distance(location1, location2):
    lat1, lon1 = location1[0], location1[1]
    lat2, lon2 = location2[0], location2[1]
    radius = 6371e3
    phi1 = lat1 * math.pi / 180
    phi2 = lat2 * math.pi / 180
    delta_phi = (lat2 - lat1) * math.pi / 180
    delta_lambda = (lon2 - lon1) * math.pi / 180
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def get_drawable_gps_data(parsed_gps_data):
    return (f"{round(parsed_gps_data.latitude, 6)}{parsed_gps_data.lat_dir},"
            f"{round(parsed_gps_data.longitude, 6)}{parsed_gps_data.lon_dir},"
            f"{'None' if parsed_gps_data.true_course is None else str(int(parsed_gps_data.true_course)).zfill(3)},"
            f"{str(int(parsed_gps_data.spd_over_grnd * 1.852)).zfill(3)}kmh")


def upload_data(file_type, file_path=None, file_data=None):
    # timeout_to_upload = 60
    detect_values = ["name", "class", "confidence", "xmin", "ymin", "xmax", "ymax"]
    global model
    model_size = device_information["detection_model"]["size"]
    try:
        if file_type == "log":
            rclone_log = subprocess.check_call(
                ["rclone", "move", file_path,
                 f"gdrive:Python/ContainerFiles/logs/"])
            if not os.path.isfile(file_path):
                logger.info(f"{file_path} uploaded to gdrive.")

            if os.path.isfile(file_path):
                logger.warning(f"{file_path} log file couldn't uploaded! Rclone Status: {rclone_log}")

        elif file_type == "image":
            if os.path.getsize(file_path) != 0:
                detection_count = 0
                result_list = []
                file_name = os.path.basename(file_path)
                with open(file_path, 'rb') as img:
                    files = {'file': (file_name, img, 'multipart/form-data', {'Expires': '0'})}

                    date_of_file = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                    file_date = date_of_file.strftime("%Y-%m-%d")
                    file_time = date_of_file.strftime("%H:%M:%S")
                    file_upload_type = "garbagedevice"

                    url_to_upload = url_harddrive + f"type={file_upload_type}&date={file_date}&time={file_time}"
                    response = RequestHandler.post(url=url_to_upload, files=files)

                if response.status_code == 200:
                    if response.json()["status"] == "success":
                        if model is None:
                            model_name = device_information["detection_model"]["name"]
                            model_size = device_information["detection_model"]["size"]

                            if not os.path.isfile(model_name):
                                logger.warning(f"{model_name} couldn't found. Trying to download from Github...")
                                model_file = requests.get(model_link + model_name)
                                if model_file.status_code == 200:
                                    with open(model_name, "wb") as model_save:
                                        model_save.write(model_file.content)
                                    logger.info(f"{model_name} downloaded and saved.")
                                else:
                                    logger.warning(f"{model_name} couldn't downloaded. "
                                                   f"Request Error: {model_file.status_code}")
                                logger.info(f"Updating {yolov5_reqs}...")
                                yolov5_reqs_update = subprocess.check_call(["pip", "install", "-r", yolov5_reqs]) == 0
                                if yolov5_reqs_update:
                                    logger.info(f"{yolov5_reqs} updated.")
                                else:
                                    logger.warning(f"{yolov5_reqs} update failed with {yolov5_reqs_update}")
                            model_load_time = time.time()
                            model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_name)
                            logger.info(f"Model loaded in {round(time.time() - model_load_time, 2)} seconds.")
                        if model is not None:
                            detection_result = model(file_path, model_size)
                            detection_count = len(detection_result.pandas().xyxy[0]["name"])
                            for i in range(detection_count):
                                result_dict = {}
                                for value in detect_values:
                                    if value == "confidence":
                                        result_dict[value] = detection_result.pandas().xyxy[0][value][i]
                                    elif value == "name":
                                        result_dict[value] = "Taken" if detection_result.pandas().xyxy[0][value][
                                                                            i] == "Alındı" else "empty"
                                    else:
                                        result_dict[value] = int(detection_result.pandas().xyxy[0][value][i])
                                result_list.append(result_dict)

                        uploaded_file = response.json()["filename"]
                        # file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                        file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                        file_data = {"file_name": uploaded_file, "date": f"{date_of_file}", "lat": file_lat,
                                     "lng": file_lng, "id": file_id, "detection": detection_count}

                        my_file_data = {"device_name": hostname, "device_type": device_type, "file_id": uploaded_file,
                                        "date": f"{date_of_file}", "lat": file_lat, "lng": file_lng,
                                        "location_id": file_id,
                                        "detection_count": detection_count, "result_list": result_list}
                        write_json(my_file_data, "uploaded_files.json")

                        response = RequestHandler.post(url=url_image + hostname, json=file_data)
                        if not response.status_code == 200:
                            logger.warning(f"Image Name couldn't uploaded! Status Code: {response.status_code}")
                            write_json(file_data, "uploaded_images.json")

                        os.remove(file_path)
                    else:
                        logger.warning(f"Image file couldn't uploaded! Status Code: {response.status_code}")

                else:
                    logger.warning(f"Image file couldn't uploaded! Status Code: {response.status_code}")

            else:
                logger.warning(f"Image File size is too small: {file_path}:{os.path.getsize(file_path)}")
                os.remove(file_path)

        elif file_type == "location":

            response = RequestHandler.post(url=url_location + hostname, json=file_data)
            if not response.status_code == 200:
                logger.warning(f"location couldn't uploaded! Status Code: {response.status_code}")
                write_json(file_data, "locations.json")

        elif file_type == "locations":
            # with open(file_path) as file:
            location_json = read_json(file_path)
            response = RequestHandler.post(url=url_location + hostname, json=location_json)
            if response.status_code == 200:
                logger.info("locations.json uploaded")
                os.remove(file_path)
            else:
                logger.warning(f"locations.json upload warning: {response.status_code}")

        elif file_type == "uploaded_images":
            # with open(file_path) as file:
            images_json = read_json(file_path)
            response = RequestHandler.post(url=url_image + hostname, json=images_json)
            if response.status_code == 200:
                logger.info("uploaded_images.json uploaded")
                os.remove(file_path)
            else:
                logger.warning(f"uploaded_images.json upload warning: {response.status_code}")

        elif file_type == "uploaded_files":
            if os.path.getsize(file_path) / 1024 > 500:
                logger.info(f"Trying to upload {file_path}")
                uploaded_files_date = datetime.datetime.now().strftime("%Y-%m-%d")
                uploaded_files_time = datetime.datetime.now().strftime("%H-%M-%S")
                uploaded_files_name = f"{uploaded_files_date}_{uploaded_files_time}_{hostname}.json"
                shutil.copy(file_path, uploaded_files_name)
                rclone_call = subprocess.check_call(["rclone", "move", uploaded_files_name,
                                                     f"gdrive:Python/ContainerFiles/files/"])
                if os.path.isfile(uploaded_files_name):
                    os.remove(uploaded_files_name)
                    logger.info(f"Rclone failed with {rclone_call}")
                else:
                    logger.info(f"'uploaded_files.json' uploaded to gdrive. Rclone returned: {rclone_call}")
                    os.remove(file_path)

    except:
        logger.error(f"Error while uploading data", exc_info=True)


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
    return f"{size:.1f}{unit}", f"{size / elapsed_time:.2f}{unit}/s"


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
                if os.path.isfile(f"{files_folder}/uploaded_images.json"):
                    upload_data(file_type="uploaded_images", file_path=f"{files_folder}/uploaded_images.json")
                if os.path.isfile(f"{files_folder}/locations.json"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.json")
                if file_to_upload.endswith(".jpg"):
                    upload_data(file_type="image", file_path=f"{files_folder}/{file_to_upload}")
        total_uploaded_file = len(files_list) - len(os.listdir(files_folder))
        if total_uploaded_file > 0:
            upload_end_time = round(time.time() - upload_start_time, 2)
            upload_end_size, ratio = file_size_unit(upload_start_size - get_folder_size(files_folder), upload_end_time)
            logger.info(f"{total_uploaded_file} files and {upload_end_size} "
                        f"uploaded in {upload_end_time} seconds. Ratio: {ratio}")
        time.sleep(60)
    except:
        logger.error(f"Error while checking folder", exc_info=True)


def listen_to_server():
    global hostname, server, server_msg, connection, stream, \
        threadKill, frame_sent, total_bytes_sent
    host = "93.113.96.30"
    port = 8181
    buff_size = 127
    alive_msg = b"$k$"

    try:
        stream = False
        frame_sent = 0
        stream_start_time = time.time()
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
                        if not stream:
                            stream = True
                            logger.info("Start to stream command received.")
                            frame_sent = 0
                            total_bytes_sent = 0
                            stream_start_time = time.time()
                            thread_list_folder = []
                            for thread_folder in threading.enumerate():
                                thread_list_folder.append(thread_folder.name)
                            if "opencv" not in thread_list_folder:
                                logger.info("Starting OpenCV")
                                threading.Thread(target=capture, name="opencv", args=("stream",), daemon=True).start()
                        else:
                            logger.warning(f"Stream was already {stream}!")

                    elif command == "stop":
                        if stream:
                            stream = False
                            # threadKill = True
                            stream_end_time = time.time() - stream_start_time
                            logger.info("Stop to stream command received.")
                            logger.info(f"Streamed: {frame_sent} frames and "
                                        f"total {round(total_bytes_sent / (1024 * 1024), 2)} mb"
                                        f" in {round(stream_end_time, 1)} in seconds")
                        else:
                            logger.warning(f"Stream was already {stream}!")

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
        time.sleep(5)
    except ConnectionRefusedError as cre:
        logger.warning(f"Connection Refused! Probably server is not online..: {cre}")
        time.sleep(5)
    except ConnectionAbortedError as cae:
        logger.warning(f"Connection closed by Client!: {cae}")
        time.sleep(5)
    except ConnectionResetError as cse:
        logger.warning(f"Connection closed by server!: {cse}")
        time.sleep(5)
    except:
        logger.error(f"Error while listening to server", exc_info=True)
        time.sleep(30)

    stream = False


class RequestHandler:
    @staticmethod
    def check_connection(url="https://cdn.atiknakit.com"):
        try:
            requests.head(url, timeout=5)
            return True
        except requests.exceptions.ConnectionError:
            pass
        except requests.Timeout:
            pass
        except:
            logger.error(f"Error while checking connection!", exc_info=True)
        return False

    @staticmethod
    def post(url, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = 60
        try:
            return requests.post(url=url, **kwargs)
        except requests.exceptions.ConnectionError:
            logging.warning("Connection Error while sending request to {}".format(url))
        except requests.Timeout:
            logger.warning("Timeout while posting to {}".format(url))
        except:
            logger.error("Error in post request to {}".format(url), exc_info=True)
        return requests.Response()

    @staticmethod
    def get(url, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = 60
        try:
            return requests.get(url=url, **kwargs)
        except requests.exceptions.ConnectionError:
            logging.warning("Connection error while getting from {}".format(url))
        except requests.Timeout:
            logging.warning("Timeout while getting from {}".format(url))
        except:
            logging.error("Error in get request to {}".format(url), exc_info=True)
        return requests.Response()


def capture(camera_mode):
    try:
        camera_path = device_information["camera-path"]
        recorded_files = "recorded"
        image_type = "jpg"
        if not os.path.isdir(recorded_files):
            os.mkdir(recorded_files)
        else:
            for old_file in glob.glob(recorded_files + "/*.jpg"):
                if os.path.getsize(old_file) / 1024 > 5:
                    shutil.move(old_file, files_folder)
                else:
                    os.remove(old_file)

        logger.info(f"Trying to open camera in {camera_mode} mode...")
        old_time = time.time()
        cap = cv2.VideoCapture(camera_path)

        frame_width, frame_height = [int(i) for i in device_information["camera-size"].split("x")]
        streaming_width = 640

        cap.set(3, frame_width)
        cap.set(4, frame_height)
        cap.set(6, 1196444237.0)

        record_width, record_height = [int(cap.get(3)), int(cap.get(4))]

        logger.info(f"Camera Opening Time: {round(time.time() - old_time, 2)} seconds")
        logger.info(f"Resolution: {record_width}x{record_height} - FPS: {cap.get(5)}")

        global save_picture
        global filename
        global threadKill
        global frame_count
        global stream
        global pass_the_id
        global take_picture
        global frame_sent
        global total_bytes_sent

        saved_pictures_count = 0
        saved_pictures_size = 0

        while True:
            ret, img = cap.read()
            if not ret:
                try:
                    camera_is = subprocess.call(["ls", "/dev/video0"])
                    logger.warning(f"ret was {ret}: {camera_is}")
                    time.sleep(10)

                except:
                    logger.error("Camera not Found!", exc_info=True)
                    time.sleep(10)

                break
            img = imutils.rotate(img, device_information["rotate"])
            if stream:
                try:
                    frame = imutils.resize(img, width=streaming_width)

                    frame = draw_text_and_rectangle(frame,
                                                    datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
                                                    x=20, y=20)
                    if drawable_gps_data is not None:
                        frame = draw_text_and_rectangle(frame, drawable_gps_data, x=20, y=frame.shape[0] - 40)

                    encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    bosluk = b"$"
                    message = bosluk + base64.b64encode(buffer) + bosluk
                    total_bytes_sent += len(message)
                    server.sendall(message)
                    frame_sent += 1
                except:
                    logger.error("Error while streaming!", exc_info=True)
                    stream = False

            if save_picture and frame_count < 400:
                image_file_path = f'{recorded_files}/{filename}.{image_type}'
                save_picture = False
                # logger.info(f'Taking picture...')
                my_imwrite(image_file_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 50])

                if os.path.isfile(image_file_path):
                    file_size = os.path.getsize(image_file_path) / 1024
                    if file_size < 1:
                        logger.warning(f"File size is too small! File size: {file_size}")
                        os.remove(image_file_path)
                    else:
                        saved_pictures_count += 1
                        saved_pictures_size += file_size
                        # logger.info(f"Saved picture FileSize = {file_size} KB: {image_file_path}")
                        shutil.move(image_file_path, files_folder)
                else:
                    logger.warning(f"Opencv couldn't find the file: {image_file_path}")
                frame_count += 1
            elif frame_count >= 400:
                logger.warning(f"Picture count is high! Passing the frame..: {frame_count} and id number: {id_number}")
                pass_the_id = id_number
                take_picture = False
                save_picture = False
                time.sleep(5)
                threadKill = True

            if threadKill:
                if saved_pictures_count > 0:
                    saved_pictures_size = round(saved_pictures_size / 1024, 2)
                    logger.info(
                        f"Total {saved_pictures_count} images of {saved_pictures_size} Mb in size were recorded.")
                threadKill = False
                cap.release()
                logger.info("Camera closed.")
                break

            # cv2.waitKey(1)

    except:
        logger.error("Error in capture function!", exc_info=True)


def check_running_threads():
    global running_threads_check_time
    threads = [thread.name for thread in threading.enumerate()]
    if time.time() - running_threads_check_time > 60:
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

            # requests.get(url_check, timeout=timeout_to_download)

            connection = RequestHandler.check_connection()

            if connection:
                if "check_folder" not in check_running_threads():
                    logger.info("Checking folder...")
                    threading.Thread(target=check_folder, name="check_folder", daemon=True).start()
                if "listen_to_server" not in check_running_threads():
                    logger.info("Streaming Thread is starting...")
                    threading.Thread(target=listen_to_server, name="listen_to_server", daemon=True).start()
                # if "listen_to_me" not in check_running_threads():
                #     logger.info("listen_to_me Thread is starting...")
                #     threading.Thread(target=listen_to_me, name="listen_to_me", daemon=True).start()
                if time.time() - pTimeCheck > 7200:
                    pTimeCheck = time.time() - 7080

                    logger.info("Checking for updates...")
                    device_information = requests.get(device_informations, timeout=timeout_to_download).json()[hostname]
                    with open("config.json", "w") as save_config:
                        json.dump(device_information, save_config)
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

                    with open('values.txt', 'w') as save_jsonfile:
                        json.dump(values, save_jsonfile)
                    garbageLocations = values['garbageLocations']

                    logger.info("Values saved to Local.")
                    logger.info(f'Count of Garbage Locations: {len(garbageLocations)}')

                    # log_size = os.path.getsize(log_file_name) / (1024 * 1024)
                    # if log_size > 1:
                    #     # log_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    #     # log_time = datetime.datetime.now().strftime("%H-%M-%S")
                    #     log_file_upload = f"{files_folder}/{get_date()}{hostname}.log"
                    #     logger.info(f"Trying to copy {log_file_upload}...")
                    #     shutil.copy(log_file_name, log_file_upload)
                    #     # rclone_log = subprocess.check_call(
                    #     #     ["rclone", "move", log_file_upload,
                    #     #      f"gdrive:Python/ContainerFiles/logs/"])
                    #     # if not os.path.isfile(log_file_upload):
                    #     with open(log_file_name, 'r+') as file:
                    #         file.truncate()
                    #     logger.info(f"{log_file_upload} copied to {files_folder} folder.")
                    # if os.path.isfile(log_file_upload):
                    #     logger.warning(f"{log_file_upload} log file couldn't uploaded! Rclone Status: {rclone_log}")
                    #     os.remove(log_file_upload)

                    pTimeCheck = time.time()
                    time.sleep(20)

                    continue

        except requests.exceptions.ConnectionError:
            logger.info("There is no Internet!")
        except requests.exceptions.ReadTimeout as timeout_error:
            logger.warning(f"Download timeout in {timeout_to_download} seconds: {timeout_error}")
        except:
            logger.error("Unknown error while checking internet!", exc_info=True)

        connection = False
        time.sleep(10)


downloaded = "downloaded_file.py"
url_of_project = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/"
device_informations = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/device_informations.json"
model_link = "https://github.com/Salih800/ContainerProject/raw/main/models/"
destination = os.path.basename(__file__)
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

total_bytes_sent = 0
frame_sent = 0
vehicle_steady = False
gps_log_time = 0
files_folder = "files"
detectLocationDistance = 40
threadKill = False
filename = None
save_picture = False
id_number = None
stream = False
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
frame_count = 0
server_msg = "wait"
pass_the_id = 0
old_location_gps = [0, 0]
model = None
drawable_gps_data = None

if not os.path.isdir(files_folder):
    logger.info(f"Making {files_folder} folder")
    os.mkdir(files_folder)

try:
    device_information = requests.get(device_informations, timeout=20).json()[hostname]
    device_type = device_information["device_type"]
    gps_port = device_information["gps_port"]
    with open("config.json", "w") as config:
        json.dump(device_information, config)
    logger.info("Device Information taken from internet.")
except:
    device_information = json.loads(open('config.json', 'r').read())
    device_type = device_information["device_type"]
    gps_port = device_information["gps_port"]
    logger.info("Device Information taken from local")

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


class EmptyGPSDataError(Exception):
    """ Exception raised when there is no GPS data available. """
    pass


class InvalidGPSDataError(Exception):
    """ Exception raised when the GPS data is invalid. """
    pass


while True:
    try:
        with serial.Serial(port=gps_port, baudrate=9600, bytesize=8, timeout=1,
                           stopbits=serial.STOPBITS_ONE) as gps_data:

            parse_error_count = 0
            invalid_gps_count = 0
            empty_gps_count = 0
            max_error_count = 100

            valid_gps_data = False
            while not valid_gps_data:
                try:
                    new_data = gps_data.readline().decode()
                    if len(new_data) < 1:
                        raise EmptyGPSDataError("No GPS data available!")

                    parsed_data = pynmea2.parse(new_data)
                    if parsed_data.sentence_type == "RMC":
                        if parsed_data.status == "A":
                            valid_gps_data = True
                            break
                        else:
                            raise InvalidGPSDataError("GPS data is invalid!")

                except pynmea2.nmea.ParseError:
                    parse_error_count += 1
                    if parse_error_count >= max_error_count:
                        logging.warning(f"Parse Error happened {parse_error_count} times!")
                        break

                except InvalidGPSDataError:
                    invalid_gps_count += 1
                    if invalid_gps_count >= max_error_count:
                        logging.warning(f"Invalid GPS data happened {invalid_gps_count} times!")
                        break

                except EmptyGPSDataError:
                    empty_gps_count += 1
                    if empty_gps_count >= max_error_count:
                        logging.warning(f"Empty GPS data happened {empty_gps_count} times!")
                        break

                except:
                    logging.error("Unexpected GPS Parse error:", exc_info=True)
                    time.sleep(60)
                    break

            if valid_gps_data:
                drawable_gps_data = get_drawable_gps_data(parsed_data)
                location_gps = [parsed_data.latitude, parsed_data.longitude]
                time_gps = str(parsed_data.timestamp)
                date_gps = str(parsed_data.datestamp)
                speed_in_kmh = round(parsed_data.spd_over_grnd * 1.852, 3)
                date_local = datetime.datetime.strptime(f"{date_gps} {time_gps[:8]}",
                                                        '%Y-%m-%d %H:%M:%S') + datetime.timedelta(
                    hours=3)
                if time.time() - gps_log_time > 60:
                    gps_log_time = time.time()
                    logger.info(f'Datetime of GPS: {date_gps} {time_gps} '
                                f'and Speed: {round(speed_in_kmh, 2)} km/s')

                if time.time() - checkCurrentTime > 600:
                    checkCurrentTime = time.time()
                    if abs(datetime.datetime.now() - date_local) > datetime.timedelta(seconds=3):
                        subprocess.call(
                            ['sudo', 'date', '-s', date_local.strftime('%Y/%m/%d %H:%M:%S')])
                        logger.info("System Date Updated.")

                if time.time() - saveLocationTime > 5:
                    saveLocationTime = time.time()

                    if calculate_distance(location_gps, old_location_gps) > 20:
                        on_the_move = True
                        location_data = {"date": date_local.strftime("%Y-%m-%d %H:%M:%S"),
                                         "lat": location_gps[0],
                                         "lng": location_gps[1], "speed": speed_in_kmh}
                        old_location_gps = location_gps
                        if connection:
                            threading.Thread(target=upload_data, name="location_upload",
                                             kwargs={"file_type": "location",
                                                     "file_data": location_data},
                                             daemon=True).start()
                        else:
                            logger.info("There is no connection. Saving location to file...")
                            write_json(location_data, "locations.json")
                    else:
                        on_the_move = False

                if take_picture:
                    distance = calculate_distance(location_gps, garbageLocation[:2])
                    if distance > detectLocationDistance:
                        take_picture = False
                        logger.info(f'Garbage is out of reach. Distance is: {round(distance, 2)}')
                    elif speed_in_kmh >= 5.0:
                        # logger.info(f'Distance: {round(distance, 2)} meters')
                        continue

                if not take_picture:
                    min_distance = float("inf")
                    for garbageLocation in garbageLocations:
                        distance = calculate_distance(location_gps, garbageLocation[:2])
                        if distance < min_distance:
                            min_distance = distance
                            min_distance_location = garbageLocation

                    if min_distance < detectLocationDistance:
                        id_number = min_distance_location[2]
                        if pass_the_id == id_number:
                            continue
                        pass_the_id = 0
                        frame_count = 0
                        # id_number = garbageLocation[2]
                        take_picture = True
                        logger.info(f'Found a close garbage. '
                                    f'Distance is: {round(distance, 2)} meters and garbage_id: {id_number}')

                    if on_the_move:
                        vehicle_steady = False
                        logger.info(f'Minimum distance = {round(min_distance, 2)} meters')

                    else:
                        if calculate_distance(location_gps, santiye_location) < 200:
                            logger.info(f"Vehicle is in the station.")
                            time.sleep(30)
                        else:
                            if not vehicle_steady:
                                logger.info(f"The vehicle is steady. Location: {location_gps}")
                                vehicle_steady = True
                            if min_distance > 100:
                                time.sleep(min_distance / 20)

                if not save_picture:
                    if take_picture and speed_in_kmh < 5.0:
                        # logger.info(f'Distance: {round(distance, 2)} meters')
                        photo_date = date_local.strftime('%Y-%m-%d__%H-%M-%S,,')
                        filename = f'{photo_date}{location_gps[0]},{location_gps[1]},{id_number}'

                        save_picture = True
                        time.sleep(1)
                else:
                    is_camera = subprocess.call(["ls", "/dev/video0"])
                    take_picture = False
                    save_picture = False
                    if is_camera == 2:
                        logger.error(f"save_picture was {save_picture}: {is_camera}")
                        time.sleep(10)
                        # restart_system("error", f"save_picture was {save_picture}: {is_camera}")

                if min_distance >= 100 and not stream:
                    if "opencv" in check_running_threads():
                        logger.info("Closing camera...")
                        threadKill = True

                elif min_distance < 100 and pass_the_id == 0:
                    if "opencv" not in check_running_threads():
                        logger.info("Starting OpenCV")
                        threading.Thread(target=capture, name="opencv", args=("record",), daemon=True).start()

    except serial.serialutil.SerialException:
        logger.error("Could not open serial port!", exc_info=True)
        time.sleep(60)

    except:
        logger.error("Unexpected GPS error:", exc_info=True)
        time.sleep(5)
