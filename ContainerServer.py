import datetime
import hashlib
import logging
import os
import shutil
import sys
import time
# import gdown
import subprocess
import requests

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO, filename='server.log',
    datefmt='%Y-%m-%d %H:%M:%S')

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.ERROR, filename='server.log',
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("System started.")


def hash_check(file, blocksize=None):
    if blocksize is None:
        blocksize = 65536

    md5 = hashlib.md5()
    with open(file, "rb") as f:
        for block in iter(lambda: f.read(blocksize), b""):
            md5.update(block)
    return md5.hexdigest()


time.sleep(15)

folder_path = '/home/pi/Desktop/files/'
upload_path = '/home/pi/Desktop/ContainerFiles/'
url_upload = "https://api2.atiknakit.com/garbagedevice/"

# file_id = "15onLiJ9BRDvOac9Ocbvc-PsG59i4HimX"#
url_of_server = "https://raw.githubusercontent.com/Salih800/ContainerProject/main/ContainerServer.py"

destination = os.path.basename(__file__)
downloaded = "downloaded_file.py"
is_upload = False
updated_time = 0

code_date = datetime.datetime.fromtimestamp(os.path.getmtime(destination))
logging.info(f"Code last updated {code_date}")

while True:
    try:
        if time.time() - updated_time > 3600:
            updated_time = time.time()

            try:
                r = requests.get(url_of_server)
                if r.status_code == 200:
                    with open(downloaded, "w") as downloaded_file:
                        downloaded_file.write(r.text)
                    
                    if hash_check(destination) != hash_check(downloaded):
                        logging.info("New update found! Changing the code...")
                        shutil.move(downloaded, destination)
                        subprocess.call(["python", destination])
                        logging.info("Code change completed. Restarting...")
                        sys.exit("Shutting down")
                    else:
                        logging.info("No update found!")

                else:
                    logging.error(f"Github Error: {r.status_code}")

            except Exception:
                exception_type, exception_object, exception_traceback = sys.exc_info()
                error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
                line_number = exception_traceback.tb_lineno
                logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

        for folder in os.listdir(folder_path):
            total_picture = 0
            total_location = 0
            total_logs = 0
            pUploadTime = time.time()

            if os.listdir(folder_path + folder):
                is_upload = True
                logging.info(f"Trying the upload files in '{folder}'")
                with requests.Session() as s:
                    for file in os.listdir(folder_path + folder):

                        filename = file.split('_')
                        if not os.path.isdir(upload_path + filename[0] + '/' + folder):
                            os.makedirs(upload_path + filename[0] + '/' + folder + '/logs')
                            os.makedirs(upload_path + filename[0] + '/' + folder + '/pictures')
                            os.makedirs(upload_path + filename[0] + '/' + folder + '/locations')

                        if file.endswith('.jpg'):
                            with open(folder_path + folder + '/' + file, 'rb') as img:
                                files = {'file': (file, img, 'multipart/form-data', {'Expires': '0'})}

                                result = s.post(url_upload + folder, files=files)

                            if result.status_code == 200:
                                total_picture = total_picture + 1
                                shutil.move(os.path.join(folder_path, folder, file),
                                            os.path.join(upload_path, filename[0], folder, 'pictures'))

                            else:
                                logging.error(result.status_code)

                        elif file.endswith('.txt'):
                            with open(folder_path + folder + '/' + file, 'rb') as location_file:

                                location = {'location': (file, location_file, 'multipart/form-data', {'Expires': '0'})}
                                # logging.info("Trying to upload 'locations.txt'...")
                                result = s.post(url_upload + folder, files=location)

                            if result.status_code == 200:
                                total_location = total_location + 1
                                shutil.move(os.path.join(folder_path, folder, file),
                                            os.path.join(upload_path, filename[0], folder, 'locations'))
                                # logging.info(f"{file} uploaded.")

                            else:
                                logging.error(result.status_code)

                        elif file.endswith('.log'):
                            shutil.move(os.path.join(folder_path, folder, file),
                                        os.path.join(upload_path, filename[0], folder, 'logs'))
                            total_logs = total_logs + 1

            if total_picture > 0 or total_location > 0 or total_logs > 0:
                logging.info(f'{total_picture} Image file, {total_location} Location file and {total_logs} Log file uploaded in {round(time.time()-pUploadTime,2)} seconds')
            else:
                logging.info(f"There is no file to upload in {folder}.")

        if is_upload:
            logging.info("Trying to upload to gdrive...")
            pUploadTime = time.time()
            subprocess.check_call(["rclone", "move", f"{upload_path}/", f"gdrive:Python/ContainerFiles/"])
            logging.info(f"Gdrive upload is completed in {round(time.time()-pUploadTime,2)} seconds.")
            is_upload = False

    except Exception:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        error_file = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]
        line_number = exception_traceback.tb_lineno
        logging.error(f"Error type: {exception_type}\tError object: {exception_object}\tFilename: {error_file}\tLine number: {line_number}")

    time.sleep(600)
