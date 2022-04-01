import sys

import cv2
import os
import datetime
import numpy
import requests
import torch
import glob
import time
from PIL import Image, ImageDraw, ImageFont
import PIL


class YoloToVideo:
    def __init__(self):
        self.model_name = 'caca_yolov5s_p17526-i256-e100-b256-cache'
        self.model_conf = 0.6
        self.model_size = 256
        self.model = None  # torch.hub.load('ultralytics/yolov5', 'custom', path='weights/' + self.model_name)
        self.taken_container_count = 0
        self.taken_container = False
        self.pics_path = "E:/Google Drive/Python/ContainerFiles/2022-02-07/e4 5f 01 6b 6a f9/pictures/*.jpg"
        self.pics_list = glob.glob(self.pics_path)
        self.old_date = datetime.datetime.strptime("2021-01-01 00-00-00", "%Y-%m-%d %H-%M-%S")
        self.font = ImageFont.truetype(r'arial.ttf', 30)
        self.result_list = {}

        self.url = "https://maps.googleapis.com/maps/api/staticmap?"
        self.api_key = "AIzaSyArKCtLh9vwiDTi3c-aVs0eMDcVBbXcpoM"
        self.zoom = "15"
        self.map_size = "250x250"
        self.scale = "3"
        self.sensor = "false"
        self.mapPhoto = None
        self.url_of_map = ""
        self.coords_of_point = None

        self.pic_name = None
        self.img = None  # Image.open(self.pic_name).convert("RGBA")
        self.img_shape = None
        self.draw = None  # ImageDraw.Draw(self.img)
        self.frame_number = 0
        self.day = ""

        self.result = None
        self.timeDelta = datetime.timedelta(seconds=10)
        self.video = None

    def get_map(self):
        if not os.path.isdir("savedMaps/"):
            os.mkdir("savedMaps/")
        if not os.path.isfile("savedMaps/" + os.path.split(self.pic_name)[1]):
            self.coords_of_point = os.path.split(self.pic_name)[1].split(',,')[1].split('.jpg')[0].split(",")
            lat = self.coords_of_point[0]
            lng = self.coords_of_point[1]
            center = lat + "," + lng

            self.url_of_map = f"""{self.url + "center=" + center + "&zoom=" + self.zoom + "&size=" 
                                   + self.map_size + "&key=" + self.api_key + "&sensor=" + self.sensor + "&scale=" 
                                   + self.scale + "&markers=" + center}"""

            r = requests.get(self.url_of_map)

            with open("savedMaps/" + os.path.split(self.pic_name)[1], 'wb') as img:
                img.write(r.content)
        self.mapPhoto = Image.open("savedMaps/" + os.path.split(self.pic_name)[1]).convert("RGBA")
        return self.mapPhoto

    def draw_bounding_box(self):
        if len(self.result.pandas().xyxy[0]["name"]) > 0:
            for value in self.result.pandas().xyxy[0]:
                self.result_list[value] = self.result.pandas().xyxy[0][value][0]
            # if self.result_list["name"] == "Taken":
            if self.result_list["name"] in ["Taken", "Alındı"]:
                label = f"{self.result_list['name']} {round(self.result_list['confidence'], 2)}"
                w, h = self.font.getsize(label)
                self.draw.rectangle((self.result_list["xmin"], self.result_list["ymin"],
                                     min(self.img_shape[0] - 1, self.result_list["xmax"]),
                                     min(self.img_shape[1] - 1, self.result_list["ymax"])),
                                    outline=(255, 0, 0), width=2)

                self.draw.rectangle((self.result_list["xmin"], self.result_list["ymin"],
                                     self.result_list["xmin"] + w + 5, self.result_list["ymin"] + h + 5),
                                    outline=(255, 0, 0), width=2, fill=(255, 0, 0))

                self.draw.text((5 + self.result_list["xmin"], self.result_list["ymin"]), label, font=self.font)

    def draw_map(self):
        self.get_map()
        self.img.paste(self.mapPhoto, (int(self.img.width * 0.75), int(self.img.height * 0.08)), mask=self.mapPhoto)

    def draw_coordinates(self):
        font = ImageFont.truetype(r'arial.ttf', 20)
        self.coords_of_point = os.path.split(self.pic_name)[1].split(',,')[1].split('.jpg')[0].split(',')
        latitude = self.coords_of_point[0]
        longitude = self.coords_of_point[1]
        id_of_place = self.coords_of_point[2]

        self.draw.text((int(self.img.width * 0.755), int(self.img.height * 0.08)),
                       f"{latitude}\n{longitude}\nid={id_of_place}",
                       font=font, fill=(200, 0, 0))

    def draw_time_stamp(self):
        timestamp = os.path.split(self.pic_name)[1].split(',,')[0]
        timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%d__%H-%M-%S').strftime('%Y-%m-%d %H:%M:%S')

        self.draw.text((int(self.img.width * 0.74), int(self.img.height * 0.03)),
                       timestamp, font=self.font, fill=(0, 255, 0))

    def draw_container_count(self):
        filename = os.path.split(self.pic_name)[1]
        date_of_file = datetime.datetime.strptime(filename.split(',,')[0], "%Y-%m-%d__%H-%M-%S")

        class_name = [x for x in self.result.pandas().xyxy[0]["name"]]
        if class_name:
            if not self.taken_container:
                self.taken_container_count = self.taken_container_count + 1
            self.taken_container = True
            self.old_date = date_of_file
        elif date_of_file - self.old_date > self.timeDelta:
            self.taken_container = False
        self.draw.text((int(self.img.width * 0.75), int(self.img.height * 0.35)),
                       f"Alınan Çöp\nKonteynerı Sayısı: {self.taken_container_count}", font=self.font,
                       fill=(0, 255, 255))
        # print(f"TakenContainer: {taken_container}\tTimeDiff: {date_of_file-old_date}"
        #       f"\tTimeDelta: {timeDelta}\tTakenContainerCount: {taken_container_count}")
        # print(f"Toplanan Çöp Kutusu: {self.taken_container_count}")
        return self.taken_container_count

    def write_to_video(self):
        self.video.write(cv2.cvtColor(numpy.array(self.img), cv2.COLOR_RGB2BGR))

    # def getContainerCount(self):

    def check_all(self, box=True, timestamp=True, maps=True, coord=True,
                  count=True, write=True, day="", vehicle="", max_frame=0):

        day = "2022-01-05" if day == "" else day
        vehicle = "rpi-2" if vehicle == "" else vehicle
        self.pics_path = f"E:/Google Drive/Python/ContainerFiles/{day}/{vehicle}/pictures/*.jpg"
        self.pics_list = glob.glob(self.pics_path)
        max_frame = len(self.pics_list) if max_frame <= 0 else min(len(self.pics_list), max_frame)
        if box or count:
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path='weights/' + self.model_name)
        running_time = time.time()
        for self.frame_number, self.pic_name in enumerate(self.pics_list):
            try:
                ratio = ((time.time() - running_time) / (self.frame_number + 1)) * (max_frame - self.frame_number + 1)
                self.img = Image.open(self.pic_name).convert("RGBA")
                self.img_shape = self.img.size
                self.draw = ImageDraw.Draw(self.img)
                if box or count:
                    self.result = self.model(self.pic_name, self.model_size)

                if self.frame_number < max_frame:
                    sys.stdout.write('\r' + f"Frame Number: {self.frame_number + 1}/{max_frame}\tRemaining Time: {round(ratio, 2)} seconds")
                                            # f"\tToplanan Çöp Kutusu: {self.taken_container_count}")
                    # print(f"Frame Number: {self.frame_number + 1}/{max_frame}\tRemaining Time: {round(ratio, 2)} seconds")
                    if box:
                        self.draw_bounding_box()
                    if timestamp:
                        self.draw_time_stamp()
                    if maps:
                        self.draw_map()
                    if coord:
                        self.draw_coordinates()
                    if count:
                        self.draw_container_count()
                        # print(f"Toplanan Çöp Kutusu: {self.taken_container_count}")
                        sys.stdout.write('\t' + f"Toplanan Çöp Kutusu: {self.taken_container_count}")
                    if write:
                        self.video = cv2.VideoWriter(f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_')}{vehicle}_{day}.mkv",
                                                     cv2.VideoWriter_fourcc(*'mp4v'), 10, (self.img_shape[0], self.img_shape[1]))
                        write = False
                    if self.video is not None:
                        self.write_to_video()
                else:
                    break
            except PIL.UnidentifiedImageError:
                    continue
            except OSError as os_error:
                print(os_error)
                continue
        if self.video is not None:
            self.video.release()


if __name__ == "__main__":

    YoloToVideo().check_all(max_frame=0, maps=True, day="2022-03-31", vehicle="rpi-4")
