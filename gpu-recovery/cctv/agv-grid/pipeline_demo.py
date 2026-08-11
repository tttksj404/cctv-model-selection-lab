"""End-to-end demo: plate grid + YOLOv5 ONNX + grid-cell mapping (server-side copy)."""
import cv2, json, os, sys, glob
import numpy as np
import onnxruntime as ort

CLASS_NAMES = ["BLACK","DARK_GRAY","GRAY_BIG","GRAY_SMALL","PINK","SKYBLUE","WHITE","AGV"]
BORDER, THRESH, GRID = 30, 170, 8

def order_corners(contour):
    approx = cv2.approxPolyDP(contour, 0.02*cv2.arcLength(contour, True), True)
    if len(approx) != 4: return None
    pts = approx.reshape(4,2).astype("float32"); rect = np.zeros((4,2), "float32")
    s = pts.sum(1); rect[0] = pts[s.argmin()]; rect[2] = pts[s.argmax()]
    d = np.diff(pts, axis=1); rect[1] = pts[d.argmin()]; rect[3] = pts[d.argmax()]
    return rect

def find_plate(img_rgb):
    m = img_rgb.copy()
    m[:BORDER],m[-BORDER:],m[:,:BORDER],m[:,-BORDER:] = 0,0,0,0
    gray = cv2.cvtColor(m, cv2.COLOR_RGB2GRAY)
    th = np.where(gray <= THRESH, 0, gray).astype(np.uint8)
    cs,_ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs: return None
    return order_corners(max(cs, key=cv2.contourArea))

def draw_grid(img, c):
    tl,tr,br,bl = c; out = img.copy()
    for i in range(GRID+1):
        r = i/GRID
        cv2.line(out, tuple((tl+(bl-tl)*r).astype(int)), tuple((tr+(br-tr)*r).astype(int)), (0,255,0), 1)
        cv2.line(out, tuple((tl+(tr-tl)*r).astype(int)), tuple((bl+(br-bl)*r).astype(int)), (0,255,0), 1)
    return out

def to_cell(pt, M):
    g = cv2.perspectiveTransform(np.array([[pt]], "float32"), M)[0,0]
    if not (0 <= g[0] < GRID and 0 <= g[1] < GRID): return None
    r, c = int(g[1]), int(g[0]); return r, c, r*GRID+c

def letterbox(img, size=640):
    h,w = img.shape[:2]; s = size/max(h,w); nh,nw = round(h*s), round(w*s)
    px,py = (size-nw)//2, (size-nh)//2
    out = np.full((size,size,3), 114, np.uint8)
    out[py:py+nh, px:px+nw] = cv2.resize(img,(nw,nh))
    return out, s, px, py

def nms(b, sc, t=0.45):
    x1,y1,x2,y2 = b.T; a = (x2-x1)*(y2-y1); o = sc.argsort()[::-1]; keep=[]
    while o.size:
        i = o[0]; keep.append(i)
        xx1,yy1 = np.maximum(x1[i],x1[o[1:]]), np.maximum(y1[i],y1[o[1:]])
        xx2,yy2 = np.minimum(x2[i],x2[o[1:]]), np.minimum(y2[i],y2[o[1:]])
        inter = np.maximum(0,xx2-xx1)*np.maximum(0,yy2-yy1)
        o = o[1:][inter/(a[i]+a[o[1:]]-inter+1e-9) <= t]
    return keep

sess = ort.InferenceSession(sys.argv[1], providers=["CPUExecutionProvider"])
iname = sess.get_inputs()[0].name
os.makedirs(os.path.expanduser("~/agv-grid/demo_out"), exist_ok=True)
results = {}
for p in sorted(glob.glob(os.path.expanduser("~/agv-grid/dataset/test/images/*.jpg"))):
    img = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
    corners = find_plate(img)
    pad, s, px, py = letterbox(img)
    blob = pad.astype(np.float32).transpose(2,0,1)[None]/255.0
    pred = sess.run(None, {iname: blob})[0][0]
    sc = pred[:,4:5]*pred[:,5:]; cid = sc.argmax(1); conf = sc[np.arange(len(sc)),cid]
    m = conf >= 0.4
    dets = []
    if m.any():
        cw = pred[m,:4]; conf, cid = conf[m], cid[m]
        b = np.stack([cw[:,0]-cw[:,2]/2, cw[:,1]-cw[:,3]/2, cw[:,0]+cw[:,2]/2, cw[:,1]+cw[:,3]/2], 1)
        for i in nms(b, conf):
            x1,y1,x2,y2 = (b[i]-[px,py,px,py])/s
            dets.append((float(x1),float(y1),float(x2),float(y2),float(conf[i]),int(cid[i])))
    M = None
    if corners is not None:
        dst = np.array([[0,0],[GRID,0],[GRID,GRID],[0,GRID]], "float32")
        M = cv2.getPerspectiveTransform(corners, dst)
        vis = draw_grid(img, corners)
    else:
        vis = img.copy()
    recs = []
    for x1,y1,x2,y2,cf,ci in dets:
        cell = to_cell(((x1+x2)/2,(y1+y2)/2), M) if M is not None else None
        recs.append({"class": CLASS_NAMES[ci], "conf": round(cf,3), "cell": cell})
        lbl = CLASS_NAMES[ci] + (f" #{cell[2]}" if cell else "")
        cv2.rectangle(vis, (int(x1),int(y1)), (int(x2),int(y2)), (255,0,0), 1)
        cv2.putText(vis, lbl, (int(x1),int(y1)-3), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255,0,0), 1)
    name = os.path.basename(p)
    results[name] = {"plate": corners is not None, "objects": recs}
    cv2.imwrite(os.path.expanduser("~/agv-grid/demo_out/")+name, cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
json.dump(results, open(os.path.expanduser("~/agv-grid/demo_out/summary.json"), "w"), indent=1)
ok = sum(1 for v in results.values() if v["plate"])
print(f"plate found: {ok}/{len(results)}; objects/img avg: {sum(len(v['objects']) for v in results.values())/len(results):.1f}")
