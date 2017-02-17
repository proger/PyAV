import sys
sys.path.insert(0, '../')

import os
import socket
import av
import av.logging
from av.video.frame import VideoFrame
from PIL import Image

import librtmp
import librtmp.logging
import cv2
import time


librtmp.logging.set_log_output(sys.stdout)
librtmp.logging.set_log_level(librtmp.logging.LOG_ALL)

conn = librtmp.RTMP("rtmp://10.0.0.130/myapp/monkey", live=True)
conn.connect()
stream = conn.create_stream(writeable=True)


test = open('test.flv','w')

def resource(filename):
    return os.path.join('../', filename)

class BlackHole(object):
    def read(self, *args, **kwargs):
        raise NotImplementedError('WE DO NOT READ HERE')

    def seek(self, *args, **kwargs):
        print 'seek', args
        return 0
        #raise NotImplementedError('WE DO NOT SEEK HERE')

    def tell(self, *args, **kwargs):
        raise NotImplementedError('WE DO NOT TELL HERE')
        return 0

    def write(self, data):
        l = len(data)
        #print data
        #print 'ABOUT TO WRITE', l
        sw = -42
        try:
            sw = stream.write(data)
        except Exception as e:
            print e
            raise
        tw = test.write(data)
        print 'WE ARE WRITING BYTES OMG', l, sw, tw, stream
        return l


class opendup(object):
    def __init__(self, i, o):
        self.i = i
        self.o = BlackHole() if not o else o

    def __enter__(self):
        self.iav = av.open(self.i)
        self.oav = av.open(self.o, 'w', format='flv')
        for s in self.iav.streams:
            # needs my fork
            self.oav.add_stream(codec_name=s.name, template=s)
        return self.iav, self.oav

    def __exit__(self, *args):
        #self.iav.close()
        self.oav.close()

def encmux(output_file, o, frame):
    p = o.encode(frame)
    if p:
        print 'mux!'
        output_file.mux(p)

def avdemux(input_file):
    input_audio_stream = next((s for s in input_file.streams if s.type == 'audio'), None)
    input_video_stream = next((s for s in input_file.streams if s.type == 'video'), None)

    for packet in input_file.demux([s for s in (input_video_stream, input_audio_stream) if s]):
        for frame in packet.decode():
            yield (packet, frame)

def ingest(input_file, output_file, overlays):
    output_audio_stream = next((s for s in output_file.streams if s.type == 'audio'), None)
    output_video_stream = next((s for s in output_file.streams if s.type == 'video'), None)

    for packet, frame in avdemux(input_file):
        frame.pts = None

        if packet.stream.type == b'audio':
            #encmux(output_file, output_audio_stream, frame)
            continue

        overlay = next(overlays, None)
        if overlay:
           image = frame.to_image()
           image.paste(overlay, (10, 10))

        newframe = VideoFrame.from_image(image).reformat(format=frame.format.name)
        #print output_video_stream, newframe
        encmux(output_file, output_video_stream, newframe)

def avremux(i, o):
    for packet, frame in avdemux(i):
        print packet, frame
        o.mux(packet)

class changesocket(object):
    def __init__(self, port):
        self.port = port
    def __enter__(self):
        host = socket.gethostbyname(socket.gethostname())
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, self.port))
        s.setblocking(False)
        s.listen(128)
        self.s = s
        return self.s
    def __exit__(self, *args):
        self.s.close()

def changeaccept(server):
    try:
        client, _ = server.accept()
    except:
        return None
    client.setblocking(True)
    thing = client.recv(4096)
    client.close()
    return thing.strip()

current_image = Image.open(resource('doge.jpg')).resize((100, 100))
def images(sock):
    """
    produce a sequence of overlay Image objects, modifiable by sockets
    """
    global current_image
    newimage = changeaccept(sock)
    if newimage:
        current_image = Image.open(newimage).resize((500,500))
    yield current_image

#defi = '/Users/vladki/Movies/demo.mov'
#defo = '/tmp/output.mov'
#defi = '../rgb_rotate.mov'
defi = '../sandbox/rgb_rotate.mp4'
defo = None
#defo = 'rtmp://10.0.0.130/myapp/donkey'

def go():
    if 'get_ipython' in globals():
        i, o = defi, defo
    else:
        i, o = sys.argv[1:3]
    with changesocket(port=12312) as s:
        with opendup(i, o) as (ai, ao):
            #avremux(ai, ao)
            ingest(ai, ao, images(s))
            print 'ingest done'

if __name__ == '__main__':
    go()
