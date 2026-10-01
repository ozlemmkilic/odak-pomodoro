"""Generate the project's vector-like clock mark, no external imagery."""
from pathlib import Path
from PIL import Image, ImageDraw

def icon(size):
    scale=4; n=size*scale
    im=Image.new('RGBA',(n,n),(15,18,27,255)); d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,n-1,n-1),radius=n*.22,fill='#0f121b')
    d.ellipse((n*.19,n*.19,n*.81,n*.81),outline='#2cff05',width=max(2,int(n*.065)))
    d.line([(n*.50,n*.32),(n*.50,n*.50),(n*.65,n*.59)],fill='#2cff05',width=max(2,int(n*.055)))
    d.ellipse((n*.466,n*.466,n*.534,n*.534),fill='#2cff05')
    return im.resize((size,size),Image.Resampling.LANCZOS)

if __name__=='__main__':
    here=Path(__file__).resolve().parent
    assets=here/'Assets'; assets.mkdir(exist_ok=True)
    for name,size in [('StoreLogo',50),('Square44x44Logo',44),('Square150x150Logo',150),('ListingIcon',300)]:
        icon(size).save(assets/(name+'.png'))
    icon(256).save(here/'odak.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
