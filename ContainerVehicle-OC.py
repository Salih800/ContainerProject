import base64
import datetime
import glob
import hashlib
# import io
import json
import logging
import os
import shutil
import socket
import subprocess
from subprocess import PIPE, run
import sys
import threading
import time

hostname = subprocess.check_output(["hostname"]).decode("utf-8").strip("\n")
requirements = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/requirements.txt"
yolov5_reqs = "https://raw.githubusercontent.com/ultralytics/yolov5/master/requirements.txt"
detect_values = ["name", "class", "confidence", "xmin", "ymin", "xmax", "ymax"]
upload_folder = "upload_folder"
my_files_json = "my_files.json"

log_file_name = f"{hostname}.log"
if os.path.isfile(log_file_name):
    with open(log_file_name, "r+") as log_file:
        log_file.write("\n")

logger = logging.getLogger("mylog")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(log_file_name)
logger_fmt = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')
handler.setFormatter(logger_fmt)
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
    import torch
    from cv2 import imwrite as my_imwrite

except ModuleNotFoundError as module:
    logger.warning("Module not found: ", module.name)
    time.sleep(30)
    logger.info("Trying to install requirements.txt")
    if subprocess.check_call(["pip", "install", "-r", requirements]) == 0:
        logger.info("Modules installed")
    else:
        logger.warning("Module install failed!")


class MyApp(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.garbage_locations = None
        self.system_alive = True
        self.connection = False
        self.running_threads_check_time = 0

    def check_running_threads(self):
        if time.time() - self.running_threads_check_time > 60:
            threads = [thread.name for thread in threading.enumerate()]
            self.running_threads_check_time = time.time()
            logger.info(f"Running Threads: {threads}")
        return [thread.name for thread in threading.enumerate()]

    def update_device(self):
        command = ['git', 'pull']
        device_updated = False
        git_result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        if git_result.returncode == 0:
            logger.info(f"{git_result.stdout}")
            device_updated = True
        elif git_result.returncode == 1:
            logger.warning(f"Could not resolve host: github.com: {git_result.returncode}")
        else:
            logger.warning(f"{git_result.returncode}: {git_result.stderr}: {git_result.stdout}")

        return device_updated

    def check_internet(self):
        timeout_to_download = 20
        last_connection_time = 0
        log_last_connection = 0
        last_time_update = 0

        while self.system_alive:
            try:
                requests.get(url_check, timeout=timeout_to_download)

                if not self.connection:
                    last_connection_time = time.time()
                    logger.info("Connected to Internet.")

                self.connection = True

            except:
                self.connection = False
                if time.time() - log_last_connection > get_seconds(m=10):
                    log_last_connection = time.time()

                    logger.info(f"Device is offline. Last connection time: "
                                f"{datetime.datetime.fromtimestamp(last_connection_time)}")

            try:
                if self.connection:
                    if time.time() - last_time_update > get_seconds(h=6):

                        last_time_update = time.time()
                        logger.info("Checking for updates...")
                        self.update_device()

                        garbage_locations_list = []
                        garbage_locations_json = MyRequestsClass(request_type="get", url=url_upload + hostname)

                        # garbage_locations_json = requests.get(url_upload + hostname,
                        # timeout=timeout_to_download).json()['garbageLocations']

                        if garbage_locations_json.status_code == 200:
                            for location in garbage_locations_json.result.json()['garbageLocations']:
                                location_lat, location_lng, location_id = location
                                garbage_locations_list.append({
                                    "id": location_id,
                                    "lat": location_lat,
                                    "lng": location_lng
                                })

                            with open('garbage_locations.json', 'w') as jsonfile:
                                json.dump(garbage_locations_list, jsonfile, indent=4)
                            self.garbage_locations = garbage_locations_list

                            logger.info("Values saved to Local.")
                            logger.info(f'Count of Garbage Locations: {len(self.garbage_locations)}')
                        else:
                            logger.warning(garbage_locations_json.error)

                    if "check_folder" not in check_running_threads():
                        logger.info("Checking folder...")
                        threading.Thread(target=check_folder, name="check_folder", daemon=True).start()
                    if "listen_to_server" not in check_running_threads():
                        logger.info("Streaming Thread is starting...")
                        threading.Thread(target=listen_to_server, name="listen_to_server", daemon=True).start()

            except requests.exceptions.ConnectionError:
                if time.time() - last_connection_time > 10:
                    logger.info("There is no Internet!")

            except requests.exceptions.ReadTimeout as timeout_error:
                logger.warning(f"Download timeout in {timeout_to_download} seconds: {timeout_error}")
            except:
                logger.error("", exc_info=True)

                logger.info("There is no connection!")

            time.sleep(10)

    def check_files(self):
        try:
            total_uploaded_file = 0

            log_size = os.path.getsize(log_file_name) / (1024 * 1024)
            if log_size > 1:
                log_file_upload = f"{upload_folder}/{get_date()}{hostname}.log"
                shutil.copy(log_file_name, log_file_upload)
                with open(log_file_name, 'w') as file:
                    file.truncate()
                logger.info(f"{log_file_upload} log file copied.")

            uploaded_files_size = os.path.getsize(my_files_json) / (1024 * 1024)
            if uploaded_files_size > 1:
                my_files_upload = f"{files_folder}/{get_date()}{hostname}.json"
                shutil.move(my_files_json, my_files_upload)
                logger.info(f"{my_files_upload} json file copied.")

            if os.path.isfile(f"{files_folder}/uploaded_files.json"):
                upload_data(file_type="uploaded_files", file_path=f"{files_folder}/uploaded_files.json")

            files_list = os.listdir(files_folder)
            if len(files_list) > 0:
                logger.info(f"Files in folder: {len(files_list)}")
                upload_start_time = time.time()

                if os.path.isfile(f"{files_folder}/uploaded_images.json"):
                    upload_data(file_type="uploaded_images", file_path=f"{files_folder}/uploaded_images.json")
                if os.path.isfile(f"{files_folder}/locations.json"):
                    upload_data(file_type="locations", file_path=f"{files_folder}/locations.json")
                for file_to_upload in files_list:
                    if self.connection:
                        total_uploaded_file += 1

                        if file_to_upload.endswith(".log"):
                            rclone_log = subprocess.check_call(
                                ["rclone", "move", file_to_upload,
                                 f"gdrive:Python/ContainerFiles/logs/"])
                            if os.path.isfile(file_to_upload):
                                logger.warning(
                                    f"{log_file_upload} log file couldn't uploaded! Rclone Status: {rclone_log}")
                                os.remove(log_file_upload)

                        if file_to_upload.endswith(".jpg"):
                            upload_data(file_type="image", file_path=f"{files_folder}/{file_to_upload}")
                if total_uploaded_file > 0:
                    upload_end_time = round(time.time() - upload_start_time, 2)
                    logger.info(f"{total_uploaded_file} files and "
                                f"{upload_end_time} seconds.")
            time.sleep(60)
        except:
            logger.error(exc_info=True)
            # logger.error("", exc_info=True)
            time.sleep(60)

    def upload_data(self, file_path):
        timeout_to_upload = 60
        model_size = self.device_information["detection_model"]["size"]
        try:

            if file_path.endswith(".json"):

                if os.path.basename(file_path) == "locations.json":
                    locations_json = read_json(file_path)
                    result = MyRequestsClass(request_type="post", url=url_location + hostname, json=locations_json)
                    if result.status_code == 200:
                        logger.info("locations.json uploaded")
                        os.remove(file_path)
                    else:
                        logger.warning(f"locations.json upload warning: {result.error}")

                elif os.path.basename(file_path) == "uploaded_images.json":
                    images_json = read_json(file_path)
                    result = MyRequestsClass(request_type="post", url=url_image + hostname, json=images_json)
                    if result.status_code == 200:
                        logger.info("uploaded_images.json uploaded")
                        os.remove(file_path)
                    else:
                        logger.warning(f"uploaded_images.json upload warning: {result.error}")

            if file_path.endswith(".mp4"):
                file_name = os.path.basename(file_path)
                with open(file_path, 'rb') as video:
                    files = {'file': (file_name, video, 'multipart/form-data', {'Expires': '0'})}

                    date_of_file = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                    file_date = date_of_file.strftime("%Y-%m-%d")
                    file_time = date_of_file.strftime("%H:%M:%S")
                    file_upload_type = "garbagedevice"

                    url_to_upload = url_harddrive + f"type={file_upload_type}&date={file_date}&time={file_time}"
                    cdn_result = MyRequestsClass(request_type="post", url=url_to_upload, files=files)
                    # status_code = cdn_result.status_code
                    # status = cdn_result.result.json()["status"]

                if cdn_result.status_code == 200:
                    if cdn_result.result.json()["status"] == "success":
                        uploaded_file = cdn_result.result.json()["filename"]
                        # file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                        file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                        file_data = {"file_name": uploaded_file, "date": f"{date_of_file}",
                                     "lat": file_lat, "lng": file_lng, "id": file_id}

                        my_file_data = {"device_name": hostname, "device_type": device_type, "file_id": uploaded_file,
                                        "date": f"{date_of_file}", "lat": file_lat, "lng": file_lng, "location_id": file_id}
                        write_json(my_file_data, my_files_json)

                        try:
                            api_result = requests.post(url_image + hostname, json=file_data, timeout=timeout_to_upload)
                            if not api_result.status_code == 200:
                                logger.warning(f"Video Name couldn't uploaded! Status Code: {api_result.status_code}")
                                write_json(file_data, "uploaded_videos.json")
                        except:
                            logger.error("", exc_info=True)
                            logger.warning(f"Video Name couldn't uploaded! Saving to file...")
                            write_json(file_data, "uploaded_videos.json")

                        os.remove(file_path)

                    else:
                        logger.error(
                            f"Video file couldn't uploaded! Status Code: {cdn_result.result.status_code}"
                            f"\tStatus: {cdn_result.result.json()}")
                else:
                    logger.warning(f"cdn upload warning: {cdn_result.error}")

            if file_type == "image":
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
                    result = MyRequestsClass(request_type="post", url=url_to_upload, files=files)
                    status_code = result.status_code
                    status = result.json()["status"]

                if status_code == 200 and status == "success":
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
                                logger.warning(
                                    f"{model_name} couldn't downloaded. Request Error: {model_file.status_code}")
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
                        # detection_start_time = time.time()
                        detection_result = model(file_path, model_size)
                        detection_count = len(detection_result.pandas().xyxy[0]["name"])
                        # logger.info(f"Detection Time: {round((time.time() - detection_start_time), 2)} and count: {detection_count}")
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

                    uploaded_file = result.json()["filename"]
                    # file_date = datetime.datetime.strptime(file_name.split(",,")[0], "%Y-%m-%d__%H-%M-%S")
                    file_lat, file_lng, file_id = file_name[:-4].split(",,")[1].split(",")
                    file_data = {"file_name": uploaded_file, "date": f"{date_of_file}", "lat": file_lat,
                                 "lng": file_lng, "id": file_id, "detection": detection_count}

                    my_file_data = {"device_name": hostname, "device_type": device_type, "file_id": uploaded_file,
                                    "date": f"{date_of_file}", "lat": file_lat, "lng": file_lng, "location_id": file_id,
                                    "detection_count": detection_count, "result_list": result_list}
                    write_json(my_file_data, my_files_json)

                    try:
                        result = requests.post(url_image + hostname, json=file_data, timeout=timeout_to_upload)
                        if not result.status_code == 200:
                            logger.warning(f"Image Name couldn't uploaded! Status Code: {result.status_code}")
                            write_json(file_data, "uploaded_images.json")
                    except:
                        logger.error("", exc_info=True)
                        logger.warning(f"Image Name couldn't uploaded! Saving to file...")
                        write_json(file_data, "uploaded_images.json")

                    os.remove(file_path)

                else:
                    logger.error(
                        f"Image file couldn't uploaded! Status Code: {result.status_code}\tStatus: {result.json()}")

            elif file_type == "location":
                try:
                    result = requests.post(url_location + hostname, json=file_data, timeout=timeout_to_upload)
                    if not result.status_code == 200:
                        logger.warning(f"location couldn't uploaded! Status Code: {result.status_code}")
                        write_json(file_data, "locations.json")
                except requests.exceptions.ConnectionError:
                    logger.warning(f"No internet. Location couldn't uploaded! Saving to file...")
                    write_json(file_data, "locations.json")
                except requests.exceptions.ReadTimeout:
                    logger.warning(f"Connection timeout in {timeout_to_upload} seconds: {url_location}")
                    write_json(file_data, "locations.json")
                except:
                    logger.error("", exc_info=True)

                    logger.warning(f"Location couldn't uploaded! Saving to file...")
                    write_json(file_data, "locations.json")

            elif file_type == "locations":
                with open(file_path) as file:
                    location_json = json.load(file)
                result = requests.post(url_location + hostname, json=location_json, timeout=timeout_to_upload)
                if result.status_code == 200:
                    logger.info("locations.json uploaded")
                    os.remove(file_path)
                else:
                    logger.warning(f"locations.json upload warning: {result.status_code}")

            elif file_type == "uploaded_images":
                with open(file_path) as file:
                    videos_json = json.load(file)
                result = requests.post(url_image + hostname, json=videos_json, timeout=timeout_to_upload)

                if result.status_code == 200:
                    logger.info("uploaded_images.json uploaded")
                    os.remove(file_path)
                else:
                    logger.warning(f"uploaded_images.json upload warning: {result.status_code}")
            elif file_type == "uploaded_files":
                if os.path.getsize(file_path) / 1024 > 500:
                    logger.info(f"Trying to upload {file_path}")
                    uploaded_files_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    uploaded_files_time = datetime.datetime.now().strftime("%H-%M-%S")
                    uploaded_files_name = f"{uploaded_files_date}_{uploaded_files_time}_{hostname}.json"
                    shutil.copy(file_path, uploaded_files_name)
                    rclone_call = subprocess.check_call(
                        ["rclone", "move", uploaded_files_name, f"gdrive:Python/ContainerFiles/files/"])
                    if os.path.isfile(uploaded_files_name):
                        os.remove(uploaded_files_name)
                        logger.info(f"Rclone failed with {rclone_call}")
                    else:
                        logger.info(f"'uploaded_files.json' uploaded to gdrive. Rclone returned: {rclone_call}")
                        os.remove(file_path)

        except:
            logger.error("", exc_info=True)


def get_date():
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')


def get_seconds(h=0, m=0, s=0):
    r"""Sends a GET request.

       :param h: Hours
       :param m: Minutes
       :param s: Seconds
       :return: seconds in float
       :rtype: float
       """
    return datetime.timedelta(hours=h, minutes=m, seconds=s).total_seconds()


def write_json(json_data, json_file_name='locations.json'):
    json_file_path = f"{json_file_name}"
    try:
        if not os.path.isfile(json_file_path):
            data = [json_data]
        else:
            data = read_json(json_file_path)
            data.append(json_data)
        json.dump(data, open(json_file_path, "w"))

    except:
        logger.error("", exc_info=True)


def read_json(json_file):
    try:
        data = json.load(open(json_file, "r"))
    except json.decoder.JSONDecodeError as json_error:
        logger.warning(f"JSONDecodeError happened at {json_file}: {json_error.pos}. Trying to save the file...")
        data = json.loads(open(json_file).read()[:json_error.pos])
        logger.info(f"{len(data)} file info saved.")
    return data


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
                result = requests.post(**self.kwargs, timeout=60)
            if "get" == self.type:
                result = requests.get(**self.kwargs, timeout=20)
            self.status_code = result.status_code
            self.result = result
            self.error = result.text
        except:
            self.error = sys.exc_info()
            logger.error("", exc_info=True)
