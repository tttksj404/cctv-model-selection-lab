import argparse,io,json,random
from pathlib import Path
import pyarrow.parquet as parquet
import torch
from PIL import Image
from torch import nn
from transformers import CLIPModel,CLIPProcessor
A=("Female","AgeOver60","Age18-60","AgeLess18","Front","Side","Back","Hat","Glasses","HandBag","ShoulderBag","Backpack","HoldObjectsInFront","ShortSleeve","LongSleeve","UpperStride","UpperLogo","UpperPlaid","UpperSplice","LowerStripe","LowerPattern","LongCoat","Trousers","Shorts","Skirt&Dress","boots")
def load(p,n):
 t=parquet.read_table(p,columns=["image",*A]).to_pydict()
 n=min(n,len(t["image"]))
 im=[x["bytes"] for x in t["image"][:n]]
 y=torch.tensor([[int(t[k][i]) for k in A] for i in range(n)],dtype=torch.float32)
 return im,y
def itb(im,y,pr,bs,seed,shuf):
 o=list(range(len(im)))
 if shuf: random.Random(seed).shuffle(o)
 for s in range(0,len(o),bs):
  z=o[s:s+bs]
  pic=[]
  for i in z:
   with Image.open(io.BytesIO(im[i])) as q: pic.append(q.convert("RGB"))
  yield pr(images=pic,return_tensors="pt")["pixel_values"],y[z]
def feat(m,x):
 return m.visual_projection(m.vision_model(pixel_values=x).pooler_output)
def th(r,y):
 p=r.sigmoid()
 out=[]
 for c in range(y.shape[1]):
  t=y[:,c].bool()
  bv=.5
  bs=-1.
  for v in torch.arange(.1,.91,.05):
   q=p[:,c].ge(v)
   sc=float(((q&t).sum()/t.sum().clamp_min(1)+(~q&~t).sum()/(~t).sum().clamp_min(1))/2)
   if sc>bs: bs=sc; bv=float(v)
  out.append(bv)
 return torch.tensor(out)
def met(r,y,t):
 q=r.sigmoid().ge(t.view(1,-1)); z=y.bool()
 po=z.sum(0).clamp_min(1); ne=(~z).sum(0).clamp_min(1)
 ma=(((q&z).sum(0)/po+((~q)&(~z)).sum(0)/ne)/2).mean()
 ins=((q&z).sum(1).float()/(q|z).sum(1).float().clamp_min(1)).mean()
 return {"mA":float(ma),"micro":float((q==z).float().mean()),"iou":float(ins)}
def ev(m,h,bs):
 rr=[]; yy=[]
 with torch.inference_mode():
  for x,y in itb(m[0],m[1],m[2],bs,0,False):
   with torch.autocast(device_type="cuda",dtype=torch.float16): rr.append(h(feat(m[3],x.to(m[4]))).float().cpu())
   yy.append(y)
 return torch.cat(rr),torch.cat(yy)
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--root",type=Path,required=True);ap.add_argument("--checkpoint",required=True)
 ap.add_argument("--train",type=int,default=20000);ap.add_argument("--val",type=int,default=5000);ap.add_argument("--test",type=int,default=5000)
 ap.add_argument("--bs",type=int,default=128);ap.add_argument("--epochs",type=int,default=3);ap.add_argument("--out",type=Path,required=True)
 a=ap.parse_args()
 torch.manual_seed(20260723);random.seed(20260723);dev=torch.device("cuda")
 pr=CLIPProcessor.from_pretrained(a.checkpoint,local_files_only=True)
 ti,ty=load(a.root/"train.parquet",a.train);vi,vy=load(a.root/"val.parquet",a.val);xi,xy=load(a.root/"test.parquet",a.test)
 m=CLIPModel.from_pretrained(a.checkpoint,local_files_only=True).to(dev)
 for p in m.parameters(): p.requires_grad=False
 for p in m.vision_model.encoder.layers[-2:].parameters(): p.requires_grad=True
 m.visual_projection.weight.requires_grad=True
 h=nn.Linear(m.config.projection_dim,len(A)).to(dev)
 ratio=ty.mean(0).to(dev);pw=((1-ratio)/ratio.clamp_min(.001)).clamp(.5,20)
 ps=[p for p in m.parameters() if p.requires_grad]
 opt=torch.optim.AdamW([{"params":ps,"lr":1e-5},{"params":h.parameters(),"lr":1e-3}],weight_decay=.01)
 sca=torch.amp.GradScaler("cuda"); hist=[];bv=-1.;bt={}
 for ep in range(a.epochs):
  m.train();h.train()
  for x,y in itb(ti,ty,pr,a.bs,20260723+ep,True):
   x=x.to(dev);y=y.to(dev)
   with torch.autocast(device_type="cuda",dtype=torch.float16): loss=nn.functional.binary_cross_entropy_with_logits(h(feat(m,x)),y,pos_weight=pw)
   opt.zero_grad(set_to_none=True);sca.scale(loss).backward();sca.step(opt);sca.update()
  m.eval();h.eval()
  rv,yv=ev((vi,vy,pr,m,dev),h,a.bs);rt,yt=ev((xi,xy,pr,m,dev),h,a.bs)
  tt=th(rv,yv);mv=met(rv,yv,tt);mt=met(rt,yt,tt);hist.append({"epoch":ep+1,"val":mv["mA"],"test":mt["mA"]})
  if mv["mA"]>bv: bv=mv["mA"];bt=mt
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps({"status":"valid","model":"CLIP ViT-L/14 last-two-block partial fine-tune","train":a.train,"val":a.val,"test":a.test,"best_val_mA":bv,"best_test":bt,"target":.85,"passed":bt.get("mA",0)>=.85,"history":hist,"gpu":torch.cuda.get_device_name(0)},indent=2))
if __name__=="__main__": main()
