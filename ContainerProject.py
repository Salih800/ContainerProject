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
#from getmac import get_mac_address

# hello_21-12-2021
#2

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

def send_files_to_server(upload_dir):
    global pTimeLog
    folder_name = '/home/pi/Desktop/pictures/'
    # folder_name = 'C:/Users/Salih/Downloads/pictures/'
    files = os.listdir(folder_name)
    logging.info(f"Total pictures in folder {len(files)}")
    if files:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname='192.168.1.199', username='pi', password='raspberry', timeout=10)
        ssh_client.exec_command(f"mkdir Desktop/files;mkdir Desktop/files/{upload_dir}")
        ftp_client = ssh_client.open_sftp()

        oldTime = time.time()
        if time.time() - pTimeLog > 300:
            pTimeLog = time.time()
            ftp_client.put('/home/pi/Desktop/project.log', f"/home/pi/Desktop/files/{upload_dir}/{get_date()}project.log")
            logging.info("'project.log' uploaded.")
            with open('project.log', 'r+') as file:
                file.truncate()
        if os.path.isfile('locations.txt'):
            ftp_client.put('locations.txt', f"/home/pi/Desktop/files/{upload_dir}/{get_date()}locations.txt")
            os.remove('locations.txt')
            logging.info("'locations.txt' uploaded.")
        for file in files:
            ftp_client.put(f"{folder_name}{file}", f'/home/pi/Desktop/files/{upload_dir}/{file}')
            os.remove(folder_name+file)
        passedTime = time.time() - oldTime

        ftp_client.close()
        rate = len(files) / passedTime
        logging.info(f"{len(files)} Pictures uploaded in {round(passedTime,2)} seconds. Upload rate is {round(rate,2)} pictures/second")
    else:
        if time.time() - pTimeLog > 1800:
            pTimeLog = time.time()
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname='192.168.1.199', username='pi', password='raspberry', timeout=10)
            ssh_client.exec_command(f"mkdir Desktop/files;mkdir Desktop/files/{upload_dir}")
            ftp_client = ssh_client.open_sftp()

            ftp_client.put('/home/pi/Desktop/project.log',
                           f"/home/pi/Desktop/files/{upload_dir}/{get_date()}project.log")
            with open('project.log', 'r+') as file:
                file.truncate()
            logging.info("'project.log' uploaded.")

            if os.path.isfile('locations.txt'):
                ftp_client.put('locations.txt', f"/home/pi/Desktop/files/{upload_dir}/{get_date()}locations.txt")
                os.remove('locations.txt')
                logging.info("'locations.txt' uploaded.")

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
        global picture_count

        while True:
            ret, img = cap.read()
            if not ret:
                logging.error("ret was False")
                break

            if save_picture and picture_count < 400:
                save_picture = False
                logging.info(f'Taking picture...')
                startOfPictureSave = time.time()
                cv2.imwrite(picture_folder+filename, img, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                pictureSaveTime = round(time.time() - startOfPictureSave, 2)
                if os.path.isfile(picture_folder + filename):
                    file_size = round(os.path.getsize(picture_folder + filename) / 1024, 2)
                    if file_size < 1:
                        logging.warning(f"File size is too small! File size: {file_size}")
                        os.remove(picture_folder+filename)
                    else:
                        logging.info(f"Saved picture FileSize={file_size} KB in {pictureSaveTime} seconds: {filename}")
                else:
                    logging.warning(f"opencv couldn't find the file: {filename}")
                picture_count += 1
            elif picture_count >= 400:
                logging.warning(f"Picture count is high! Passing the frame..: {picture_count}")

            if threadKill:
                threadKill = False
                cap.release()
                break

            cv2.waitKey(1)

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


def internet_on():
    global connection
    global url_check
    try:
        requests.get(url_check)
        if not connection:
            connection = True
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
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")


logging.info("System started")

time.sleep(3)

downloaded = "downloaded_file.py"
url_of_project = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/ContainerProject.py"
# file_id = '1vA9bilwgRObCULgQMphCSxjQO5CT1unu'
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
connection = False
check_connection = 0

picture_count = 0
threadKill = False
filename = None
save_picture = False
hostname = "empty"
id_number = None
detectLocationDistance = 40

try:
    subprocess.check_call(["ls","/dev/ttyACM0"])
    gps_port = "/dev/ttyACM0"

except Exception as e:
    gps_port = "/dev/ttyS0"

try:
    hostname = subprocess.check_output(["hostname"]).decode("utf-8").strip("\n")

    if not os.path.isdir("pictures"):
        logging.info("Making 'pictures' folder")
        os.mkdir("pictures")

    logging.info("Getting values from local...")
    values = json.loads(open('values.txt', 'r').read())
    garbageLocations = values['garbageLocations']

except Exception:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
    line_number = exception_traceback.tb_lineno
    logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

logging.info(f"Hostname: {hostname}\tPort: {gps_port}")

while True:
    if time.time() - check_connection > 5:
        check_connection = time.time()
        logging.info("Checking Connection...")
        threading.Thread(target=internet_on, daemon=True).start()

    if time.time() - pTimeConnection > 300:
        pTimeConnection = time.time()

        code_date = datetime.datetime.fromtimestamp(os.path.getmtime(destination))
        logging.info(f"Running Code is up to date: {code_date}")

    if connection:
        try:
            if time.time() - pTimeCheck > 300:
                pTimeCheck = time.time()

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
                        sys.exit("Shutting down")
                    else:
                        logging.info("No update found!")

                else:
                    logging.warning(f"Github Error: {r.status_code}")

                values = requests.get(url_upload + hostname, timeout=timeout).json()

                with open('values.txt', 'w') as jsonfile:
                    json.dump(values, jsonfile)
                garbageLocations = values['garbageLocations']
                # cameraPictureInterval = values['cameraPictureInterval']
                # detectLocationDistance = values['detectLocationDistance']
                # locationInterval = values['locationInterval']

                logging.info("Values saved to Local.")

                logging.info(f'Count of Garbage Locations: {len(garbageLocations)}')
    
        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
            line_number = exception_traceback.tb_lineno
            logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")
    if connection:
        try:
            logging.info("Trying to upload files to Server")
            uploadStartTime = time.time()
            old_file_count = len(os.listdir(picture_folder))
            send_files_to_server(hostname)
            logging.info(f'{len(os.listdir(picture_folder)) - old_file_count} picture uploaded in {round(time.time()-uploadStartTime,2)}')
        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
            line_number = exception_traceback.tb_lineno
            logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

            logging.info(f'{old_file_count - len(os.listdir(picture_folder))} picture uploaded in {round(time.time()-uploadStartTime,2)}')
        time.sleep(30)

    if not connection:

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
                            time.sleep(5)
                        continue
                    except ValueError as verr:
                        logging.warning(f"{verr}")
                        # time.sleep(1)
                        break

            if data_type == "RMC":
                data_type = str

                if parsed_data.status == 'A':
                    location_gps = [parsed_data.latitude, parsed_data.longitude]
                    time_gps = str(parsed_data.timestamp)
                    date_gps = str(parsed_data.datestamp)
                    speed_in_kmh = parsed_data.spd_over_grnd * 1.852
                    date_local = datetime.datetime.strptime(f"{date_gps} {time_gps[:8]}", '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=3)
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
                        distance = geopy.distance.distance(location_gps, garbageLocation[:2]).meters
                        if distance > detectLocationDistance:
                            take_picture = False
                            logging.info(f'Garbage is out of reach. Distance is: {round(distance,2)}')
                        elif speed_in_kmh >= 5.0:
                            logging.info(f'Distance: {round(distance,2)} meters')

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
                                logging.info(f'Found a close garbage. Distance is: {round(distance,2)} meters')
                                break
                        minDistance = min(distances)
                        logging.info(f'Total location check time {round(time.time()-pTimeCheckLocations,2)} seconds and Minimum distance = {round(minDistance,2)} meters')
                    if not save_picture:
                        if take_picture and speed_in_kmh < 5.0:
                            logging.info(f'Distance Detection Interval: {detectLocationDistance}\tDistance: {round(distance,2)} meters')
                            photo_date = date_local.strftime('%Y-%m-%d__%H-%M-%S,,')
                            filename = f'{photo_date}{location_gps[0]},{location_gps[1]},{id_number}.jpg'

                            save_picture = True
                            # logging.warning(subprocess.call(["ls", "/dev/video0"]))
                            time.sleep(1)
                    else:
                        logging.warning(f"save_picture was {save_picture}")
                        save_picture = True
                        logging.warning(subprocess.call(["ls", "/dev/video0"]))

                    if minDistance >= 100:
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
            logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")
