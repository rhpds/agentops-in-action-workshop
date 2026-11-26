import json, itertools
class Scene:
    def __init__(self):
        self.els=[]; self._c=itertools.count(1)
        self.GREEN="#2f9e44"; self.BLUE="#1971c2"; self.AMBER="#f08c00"
        self.RED="#e03131"; self.GREY="#868e96"; self.VIOLET="#6741d9"; self.INK="#1e1e1e"
    def _b(self,**kw):
        n=next(self._c)
        d=dict(angle=0,fillStyle="solid",strokeWidth=2,strokeStyle="solid",roughness=1,
               opacity=100,groupIds=[],frameId=None,roundness=None,seed=1000+n*7919,
               version=1,versionNonce=2000+n*104729,isDeleted=False,boundElements=[],
               updated=1,link=None,locked=False,backgroundColor="transparent",
               strokeColor=self.INK,id=f"e{n}")
        d.update(kw); return d
    def text(self,x,y,s,size=16,color=None,align="left"):
        if not s or not s.strip(): return 0,0   # excalidraw drops zero-width text on restore
        lines=s.split("\n"); w=max(len(l) for l in lines)*0.56*size; h=len(lines)*1.25*size
        self.els.append(self._b(type="text",x=x,y=y,width=w,height=h,
            strokeColor=color or self.INK,text=s,fontSize=size,fontFamily=2,textAlign=align,
            verticalAlign="top",containerId=None,originalText=s,lineHeight=1.25))
        return w,h
    def box(self,x,y,w,h,stroke,fill="transparent",dashed=False):
        self.els.append(self._b(type="rectangle",x=x,y=y,width=w,height=h,strokeColor=stroke,
            backgroundColor=fill,strokeStyle="dashed" if dashed else "solid",roundness={"type":3}))
    def ellipse(self,x,y,w,h,stroke,fill="transparent"):
        self.els.append(self._b(type="ellipse",x=x,y=y,width=w,height=h,strokeColor=stroke,
            backgroundColor=fill))
    def arrow(self,pts,color=None,start=None,end="arrow",sharp=True,dashed=False):
        x0,y0=pts[0]; rel=[[p[0]-x0,p[1]-y0] for p in pts]
        xs=[p[0] for p in rel]; ys=[p[1] for p in rel]
        self.els.append(self._b(type="arrow",x=x0,y=y0,width=max(xs)-min(xs),height=max(ys)-min(ys),
            strokeColor=color or self.INK,roundness=None if sharp else {"type":2},points=rel,
            strokeStyle="dashed" if dashed else "solid",
            lastCommittedPoint=None,startBinding=None,endBinding=None,
            startArrowhead=start,endArrowhead=end))
    def save(self,path):
        json.dump({"type":"excalidraw","version":2,
                   "source":"https://github.com/rhpds/agentops-in-action-workshop",
                   "elements":self.els,
                   "appState":{"gridSize":None,"viewBackgroundColor":"#ffffff"},
                   "files":{}}, open(path,"w"), indent=1)
        return len(self.els)
