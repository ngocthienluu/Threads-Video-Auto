"""Shared deterministic editing operations, independent of Qt."""
import math

def resize_corner(before,corner,x,y):
    w,h=before["width"]*before["scale_x"],before["height"]*before["scale_y"]
    right,bottom=corner in (1,3),corner in (2,3)
    ax,ay=(0 if right else w),(0 if bottom else h)
    angle=math.radians(before["rotation"]);c,s=math.cos(angle),math.sin(angle)
    anchor_x=before["x"]+w/2+c*(ax-w/2)-s*(ay-h/2)
    anchor_y=before["y"]+h/2+s*(ax-w/2)+c*(ay-h/2)
    dx,dy=x-anchor_x,y-anchor_y
    local_x,local_y=c*dx+s*dy,-s*dx+c*dy
    vx,vy=(w if right else -w),(h if bottom else -h)
    factor=max(16/min(w,h),min(8192/max(w,h),(local_x*vx+local_y*vy)/(w*w+h*h)))
    nw,nh=w*factor,h*factor
    nax,nay=(0 if right else nw),(0 if bottom else nh)
    cx=anchor_x-c*(nax-nw/2)+s*(nay-nh/2)
    cy=anchor_y-s*(nax-nw/2)-c*(nay-nh/2)
    return dict(x=cx-nw/2,y=cy-nh/2,width=before["width"]*factor,height=before["height"]*factor)

def snap_position(x,y,width,height,threshold):
    guides=[]
    for axis,value,size,limit in (("x",x,width,1080),("y",y,height,1920)):
        choices=((0,0),(limit/2-size/2,limit/2),(limit-size,limit))
        target,guide=min(choices,key=lambda pair:abs(value-pair[0]))
        if abs(value-target)<=threshold:
            if axis=="x":x=target
            else:y=target
            guides.append((axis,guide))
    return x,y,guides
