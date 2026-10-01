"""Generate the bundled bell; no downloaded audio or network access."""
import math
import struct
import wave
from pathlib import Path

def generate():
    rate=44100
    frames=[]
    for index in range(int(rate*3.8)):
        t=index/rate
        value=0.0
        for start,pitch in ((0,880),(.65,1108.73),(1.3,1318.51)):
            dt=t-start
            if dt>=0:
                envelope=min(1,dt/.009)*math.exp(-dt*2.1)
                value+=envelope*(math.sin(2*math.pi*pitch*dt)+.26*math.sin(2*math.pi*pitch*2.76*dt))*.24
        frames.append(struct.pack('<h',int(max(-1,min(1,value))*32767)))
    with wave.open(str(Path(__file__).parent/'alarm.wav'),'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(b''.join(frames))

if __name__=='__main__':generate()
