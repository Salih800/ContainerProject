import logging
import datetime
import json
import os
import threading
import sys

import cv2
import paramiko
import subprocess
import time
import gdown

import geopy.distance
import pynmea2
import requests
import serial
from getmac import get_mac_address

# hello_21-12-2021

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO, filename='project.log',
    datefmt='%Y-%m-%d %H:%M:%S')

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.ERROR, filename='project.log',
    datefmt='%Y-%m-%d %H:%M:%S')


def send_files_to_server(mac_address):
    global pTimeLog
    folder_name = '/home/pi/Desktop/pictures/'
    # folder_name = 'C:/Users/Salih/Downloads/pictures/'
    files = os.listdir(folder_name)
    logging.info(f"Total pictures in folder {len(files)}")
    if files:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname='192.168.1.199', username='pi', password='raspberry', timeout=10)
        ssh_client.exec_command(f"mkdir Desktop/files;mkdir Desktop/files/{mac_address}")
        ftp_client = ssh_client.open_sftp()

        oldTime = time.time()
        if time.time() - pTimeLog > 300:
            pTimeLog = time.time()
            ftp_client.put('/home/pi/Desktop/project.log', f"/home/pi/Desktop/files/{mac_address}/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')}project.log")
            logging.info("'project.log' uploaded.")
            with open('project.log', 'r+') as file:
                file.truncate()
        if os.path.isfile('locations.txt'):
            ftp_client.put('/home/pi/Desktop/locations.txt', f"/home/pi/Desktop/files/{mac_address}/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')}locations.txt")
            os.remove('/home/pi/Desktop/locations.txt')
            logging.info("'locations.txt' uploaded.")
        for file in files:
            ftp_client.put(folder_name+file, f'/home/pi/Desktop/files/{mac_address}/'+file)
            os.remove(folder_name+file)
        passedTime = time.time() - oldTime

        ftp_client.close()
        rate = len(files) / passedTime
        logging.info(f"{len(files)} Pictures uploaded in {round(passedTime,2)} seconds. Upload rate is {round(rate,2)} pictures/second")
    else:
        if time.time() - pTimeLog > 300:
            pTimeLog = time.time()
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname='192.168.1.199', username='pi', password='raspberry', timeout=10)
            ssh_client.exec_command(f"mkdir Desktop/files;mkdir Desktop/files/{mac_address}")
            ftp_client = ssh_client.open_sftp()

            ftp_client.put('/home/pi/Desktop/project.log', f"/home/pi/Desktop/files/{mac_address}/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')}project.log")
            with open('project.log', 'r+') as file:
                file.truncate()
            logging.info("'project.log' uploaded.")

            ftp_client.close()

        logging.info("No files to upload.")


def capture():
    try:
        logging.info("Trying to open camera")
        oldTime = time.time()
        cap = cv2.VideoCapture(0)
        cap.set(3, 1280)
        cap.set(4, 960)

        logging.info(f"Camera Opening Time: {round(time.time()-oldTime,2)}")

        global save_picture
        global filename
        global picture_folder
        global threadKill

        while True:
            ret, img = cap.read()
            if not ret:
                logging.error("ret was False")
                break

            if save_picture:
                save_picture = False
                logging.info(f'Taking picture...')
                startOfPictureSave = time.time()
                cv2.imwrite(picture_folder+filename, img, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                pictureSaveTime = round(time.time() - startOfPictureSave, 2)
                fileSize = round(os.path.getsize(picture_folder + filename) / 1024, 2)
                logging.info(f"Saved picture FileSize={fileSize} KB in {pictureSaveTime} seconds: {filename}")

            if threadKill:
                threadKill = False
                break

            cv2.waitKey(1)

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


logging.info("System started")

time.sleep(15)

file_id = '1vA9bilwgRObCULgQMphCSxjQO5CT1unu'
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
url_check = "https://api2.atiknakit.com/garbagedeviceHistory"
url_upload = "https://api2.atiknakit.com/garbagedevice/"
timeout = 10
picture_folder = "pictures/"

threadKill = False
filename = None
save_picture = False
# threading.Thread(target=capture,name="opencv").start()

try:
    if not os.path.isdir("pictures"):
        logging.info("Making 'pictures' folder")
        os.mkdir("pictures")

    logging.info("Getting values from local")
    values = json.loads(open('values.txt', 'r').read())
    cameraPictureInterval = values['cameraPictureInterval']
    detectLocationDistance = values['detectLocationDistance']
    garbageLocations = values['garbageLocations']
    locationInterval = values['locationInterval']
except Exception:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
    line_number = exception_traceback.tb_lineno
    logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


while True:
    mac_address = get_mac_address()

    if time.time() - pTimeConnection > 300:
        pTimeConnection = time.time()
        logging.info(f"Running Code is up to date: 2022-02-01 14:00:00\tMac Address: {mac_address}")

    if mac_address is not None:
        try:
            if time.time() - pTimeCheck > 300:
                pTimeCheck = time.time()

                gdown.download(id=file_id, output=destination)

                logging.info("Code has been updated. Getting values from Internet..")

                values = requests.get(url_upload + mac_address, timeout=timeout).json()

                with open('values.txt', 'w') as jsonfile:
                    json.dump(values, jsonfile)
                cameraPictureInterval = values['cameraPictureInterval']
                detectLocationDistance = values['detectLocationDistance']
                garbageLocations = values['garbageLocations']
                locationInterval = values['locationInterval']

                logging.info("Values saved to Local. Connected to the Internet.")

                logging.info(f'Count of Garbage Locations: {len(garbageLocations)}')

        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
            line_number = exception_traceback.tb_lineno
            logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

    if mac_address is not None:
        try:
            logging.info("Trying to upload files to Server")
            uploadStartTime = time.time()
            old_file_count = len(os.listdir(picture_folder))
            send_files_to_server(mac_address)
            logging.info(f'{len(os.listdir(picture_folder)) - old_file_count} picture uploaded in {round(time.time()-uploadStartTime,2)}')
        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
            line_number = exception_traceback.tb_lineno
            logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

            logging.info(f'{old_file_count - len(os.listdir(picture_folder))} picture uploaded in {round(time.time()-uploadStartTime,2)}')
        time.sleep(30)

    if mac_address is None:

        try:
            while data_type != 'RMC':
                with serial.Serial(port="/dev/ttyACM0", baudrate=9600, bytesize=8, timeout=1,
                                   stopbits=serial.STOPBITS_ONE) as gps_data:
                    new_data = gps_data.readline().decode('utf-8', errors='replace')

                    for msg in reader.next(new_data):
                        parsed_data = pynmea2.parse(str(msg))
                        data_type = parsed_data.sentence_type

            if data_type == "RMC":
                data_type = str
                logging.info(f'Received GPS Data: {str(new_data)}')

                if parsed_data.status == 'A':
                    location_gps = [parsed_data.latitude, parsed_data.longitude]
                    time_gps = str(parsed_data.timestamp)
                    logging.info(f"GPS Time: {time_gps}")
                    date_gps = str(parsed_data.datestamp)
                    speed_in_kmh = parsed_data.spd_over_grnd * 1.852
                    date_local = datetime.datetime.strptime(f"{date_gps} {time_gps}", '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=3)
                    logging.info(f'Datetime of GPS: {date_gps} {time_gps} and Speed: {round(speed_in_kmh,2)} km/s')

                    if time.time() - checkCurrentTime > 600:
                        if abs(datetime.datetime.now() - date_local) > datetime.timedelta(seconds=3):
                            subprocess.call(['sudo', 'date', '-s', date_local.strftime('%Y/%m/%d %H:%M:%S')])
                            logging.info("System Date Updated.")

                    if time.time() - saveLocationTime > 5:
                        saveLocationTime = time.time()
                        with open('locations.txt', 'a') as locations_file:
                            locations_file.write(f'{date_local} {location_gps[0]},{location_gps[1]} {round(speed_in_kmh,3)}')
                            locations_file.write('\n')

                    if take_picture:
                        distance = geopy.distance.distance(location_gps, garbageLocation).meters
                        if distance > detectLocationDistance + 100:
                            take_picture = False
                            logging.info(f'Garbage is out of reach. Distance is: {round(distance,2)}')
                        elif speed_in_kmh >= 5.0:
                            logging.info(f'Distance: {round(distance,2)}')

                    if not take_picture:
                        distances = []
                        pTimeCheckLocations = time.time()
                        for garbageLocation in garbageLocations:
                            distance = geopy.distance.distance(location_gps, garbageLocation).meters
                            distances.append(distance)
                            if distance < detectLocationDistance + 100:
                                take_picture = True
                                logging.info(f'Found a close garbage. Distance is: {round(distance,2)}')
                                break
                        minDistance = min(distances)
                        logging.info(f'Total location check time {round(time.time()-pTimeCheckLocations,2)} seconds and Minimum distance = {round(minDistance,2)} meters')
                    if not save_picture:
                        if take_picture and speed_in_kmh < 5.0:
                            logging.info(f'Distance Detection Interval: {detectLocationDistance}\tDistance: {round(distance,2)}')
                            photo_date = date_local.strftime('%Y-%m-%d__%H-%M-%S,,')
                            filename = f'{photo_date}{location_gps[0]},{location_gps[1]}.jpg'

                            save_picture = True

                            time.sleep(1)
                    else:
                        logging.error(f"save_picture was {save_picture}")

                    if minDistance >= 200:
                        for thread in threading.enumerate():
                            if thread.name == "opencv":
                                logging.info("Killing OpenCV")
                                threadKill = True
                    # if minDistance >= 100:
                    # time.sleep(minDistance/20)
                    else:
                        thread_list = []
                        for thread in threading.enumerate():
                            thread_list.append(thread.name)
                        if "opencv" not in thread_list:
                            logging.info("Starting OpenCV")
                            threading.Thread(target=capture, name="opencv").start()

                elif parsed_data.status == 'V':
                    logging.info(f'Invalid GPS info!!: {parsed_data.status}')
                    time.sleep(5)
        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
            line_number = exception_traceback.tb_lineno
            logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")