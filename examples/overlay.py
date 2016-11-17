import sys
sys.path.insert(0, '../')

import os
import socket
import av
import av.logging
from av.video.frame import VideoFrame
from PIL import Image

def resource(filename):
    return os.path.join('../', filename)

class opendup(object):
    def __init__(self, i, o):
        self.i = i
        self.o = o

    def __enter__(self):
        self.iav = av.open(self.i)
        self.oav = av.open(self.o, 'w')
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
            encmux(output_file, output_audio_stream, frame)
            continue

        overlay = next(overlays, None)
        if overlay:
           image = frame.to_image()
           image.paste(overlay, (200, 200))

        newframe = VideoFrame.from_image(image).reformat(format=frame.format.name)
        print output_video_stream, newframe
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

current_image = Image.open(resource('doge.jpg')).resize((500, 500))
def images(sock):
    """
    produce a sequence of overlay Image objects, modifiable by sockets
    """
    global current_image
    newimage = changeaccept(sock)
    if newimage:
        current_image = Image.open(newimage).resize((500,500))
    yield current_image

defi = '/Users/vladki/Movies/demo.mov'
defo = '/tmp/output.mov'

def go():
    if 'get_ipython' in globals():
        i, o = defi, defo
    else:
        i, o = sys.argv[1:3]
    with changesocket(port=12312) as s:
        with opendup(i, o) as (ai, ao):
            #avremux(ai, ao)
            ingest(ai, ao, images(s))

if __name__ == '__main__':
    go()
