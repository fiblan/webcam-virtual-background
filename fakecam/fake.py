import os
import cv2
import numpy as np
import requests
import pyfakewebcam
import getopt
from signal import signal, SIGINT
from sys import argv, exit

height, width = 720, 1280
rem_mask = None
rem = 10

def load_background_image(width,height):
    # load the virtual background
    background = cv2.imread("background.jpg")
    background = cv2.resize(background, (width, height))
    return background


def handler(signal_received):
    global width,height 
    load_background_image( width,height)
    print('Reloaded the background image')

def get_mask(frame, sf, bodypix_url='http://127.0.0.1:9000'):
    # cv2.imshow('FrameinMask',frame)
    # cv2.waitKey(10)
    frame = cv2.resize(frame, (0, 0), fx=sf, fy=sf)
    _, data = cv2.imencode(".png", frame)
    r = requests.post(
        url=bodypix_url,
        data=data.tobytes(),
        headers={'Content-Type': 'application/octet-stream'})
    mask = np.frombuffer(r.content, dtype=np.uint8)
    mask = mask.reshape((frame.shape[0], frame.shape[1]))
    mask = cv2.resize(mask, (0, 0), fx=1/sf, fy=1/sf,
                      interpolation=cv2.INTER_NEAREST)
    mask = cv2.dilate(mask, np.ones((15,15), np.uint8) , iterations=1)
    mask = cv2.blur(mask.astype(float), (50,50))
    # cv2.imshow("MASK", mask)
    return mask

def get_frame(cap, background, sf):
    global rem_mask
    global rem
    _, frame = cap.read()
    # fetch the mask with retries (the app needs to warmup and we're lazy)
    # e v e n t u a l l y c o n s i s t e n t
    mask = None
    if(rem_mask is None):
        rem = 0
        while mask is None:
            try:
                mask = get_mask(frame,sf)
                rem_mask = mask
            except:
                 print("mask request failed, retrying")
    else:
        mask = rem_mask
        rem+=1
        if(rem>30):
            rem_mask = None
        # print(rem)
    # composite the background
    for c in range(frame.shape[2]):
        frame[:,:,c] = frame[:,:,c] * mask + background[:,:,c] * (1 - mask)

    return frame


def main():
    global width, height
    backgroundType = 'image'
    try:
        opts, args = getopt.getopt(argv[1:],"ht:v",["type"])
    except getopt.GetoptError:
        print('python fake.py [-t <image|video>]')
        exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('python fake.py [-t <image|video>]')
            exit()
        elif opt in ("-t", "--type"):
            backgroundType = arg
 
    print(backgroundType)
    # setup access to the *real* webcam
    cap = cv2.VideoCapture('/dev/video0')
    capvideo = cv2.VideoCapture('video.mp4')

    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # In case the real webcam does not support the requested mode.
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    # The scale factor for image sent to bodypix
    sf = 0.5

    # setup the fake camera
    fake = pyfakewebcam.FakeWebcam('/dev/video2', width, height)

    # declare global variables
    background = None

    # if backgroudType
    background = load_background_image(width, height)
    signal(SIGINT, handler)
    print('Running...')
    print('Please press CTRL-\ to exit.')
    print('Please CTRL-C to reload the background image')
    # frames forever
    while True:
        if backgroundType == 'video':
            ret, background2 = capvideo.read() 

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            if ret:
                background2 = cv2.resize(background2, (width, height))
                # cv2.imshow("Image", background2)
                background2Prev = background2
            else:
                print('no video')
                capvideo.set(cv2.CAP_PROP_POS_FRAMES, 0)
                background2 = background2Prev
            background = background2

        # cv2.imshow("BackgroundImage", background)
        # cv2.waitKey(100)
        frame = get_frame(cap, background, sf)
        # fake webcam expects RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # cv2.imshow("Post", frame)

        fake.schedule_frame(frame)

if __name__ == '__main__':
    main()
   
