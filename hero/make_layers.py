import sys
from PIL import Image, ImageDraw, ImageFilter
cut = Image.open(sys.argv[1]).convert('RGBA'); out = sys.argv[2]
W,H = cut.size
# soften the straight photo edges (right + bottom) so the sticker outline fades out there
import numpy as np
a0 = np.array(cut.getchannel('A')).astype(float)
ys = np.clip((H-1-np.arange(H))/60.0,0,1)[:,None]; xs = np.clip((W-1-np.arange(W))/28.0,0,1)[None,:]
cut.putalpha(Image.fromarray((a0*ys*xs).astype('uint8')))
# Jaw piece: everything below the lip line, around the chin (incl. finger tip)
jaw_poly = [(203,302),(220,300),(238,301),(255,299),(268,296),(282,300),(292,312),
            (294,326),(284,340),(262,350),(240,350),(222,346),(208,336),(198,318)]
m = Image.new('L',(W,H),0); ImageDraw.Draw(m).polygon(jaw_poly, fill=255)
m = m.filter(ImageFilter.GaussianBlur(0.6))
a = cut.getchannel('A')
from PIL import ImageChops
jaw = cut.copy(); jaw.putalpha(ImageChops.multiply(a, m))
head = cut.copy(); head.putalpha(ImageChops.multiply(a, ImageChops.invert(m)))
# Mouth cavity: dark shape just under the lip line, revealed when the jaw drops
cav = Image.new('RGBA',(W,H),(0,0,0,0))
ImageDraw.Draw(cav).polygon([(207,301),(238,301),(267,297),(276,302),(268,318),(238,322),(212,316)], fill=(30,12,14,255))
cav = cav.filter(ImageFilter.GaussianBlur(1.2))
for name,img in (('full',cut),('head',head),('jaw',jaw),('mouth',cav)):
    img.save(f'{out}/{name}.webp', 'WEBP', quality=90, method=6)
print('ok')
