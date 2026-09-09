from flask import Flask,request,jsonify
import sqlite3,secrets,hashlib,os,calendar
from datetime import datetime,timezone
app=Flask(__name__); DB=os.environ.get("ACTIVATION_DB","licenses.db"); TOKEN=os.environ.get("ACTIVATION_ADMIN_TOKEN","CHANGE_THIS")
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute("""CREATE TABLE IF NOT EXISTS licenses(id INTEGER PRIMARY KEY,key_hash TEXT UNIQUE,product TEXT,months INTEGER,created_at TEXT,expires_at TEXT,machine_id TEXT,activated_at TEXT,active INTEGER DEFAULT 1)""");c.commit();return c
def h(k):return hashlib.sha256(k.strip().upper().encode()).hexdigest()
def addm(dt,n):
 m=dt.month-1+n;y=dt.year+m//12;mo=m%12+1;day=min(dt.day,calendar.monthrange(y,mo)[1]);return dt.replace(year=y,month=mo,day=day)
def mk(): 
 x=secrets.token_hex(12).upper();return "ACS3-"+"-".join(x[i:i+6] for i in range(0,24,6))
@app.get("/health")
def health():return jsonify(ok=True)
@app.post("/activate")
def activate():
 d=request.get_json(silent=True) or {};k=str(d.get("key","")).strip().upper();p=str(d.get("product","AI-CAMERA-STUDIO"));mid=str(d.get("machine_id",""))
 c=db();r=c.execute("SELECT * FROM licenses WHERE key_hash=? AND product=? AND active=1",(h(k),p)).fetchone()
 if not r:c.close();return jsonify(ok=False,message="Invalid or disabled activation key."),403
 now=datetime.now(timezone.utc)
 if r["machine_id"] and r["machine_id"]!=mid:c.close();return jsonify(ok=False,message="This key is already activated on another PC."),409
 if r["expires_at"]:
  exp=datetime.fromisoformat(r["expires_at"].replace("Z","+00:00"))
  if exp<=now:c.close();return jsonify(ok=False,message="This activation key has expired."),403
 else:
  exp=addm(now,r["months"]);c.execute("UPDATE licenses SET expires_at=?,machine_id=?,activated_at=? WHERE id=?",(exp.isoformat().replace("+00:00","Z"),mid,now.isoformat().replace("+00:00","Z"),r["id"]));c.commit()
 c.close();return jsonify(ok=True,license_id=r["id"],expires_at=exp.isoformat().replace("+00:00","Z"),activated_at=r["activated_at"] or now.isoformat().replace("+00:00","Z"))
@app.post("/validate")
def validate():
 d=request.get_json(silent=True) or {}; lid=d.get("license_id"); mid=str(d.get("machine_id",""))
 if not lid or not mid: return jsonify(ok=False,message="Missing license or machine information."),400
 c=db(); r=c.execute("SELECT * FROM licenses WHERE id=? AND active=1",(int(lid),)).fetchone()
 if not r: c.close(); return jsonify(ok=False,message="License is invalid or disabled."),403
 if r["machine_id"] and r["machine_id"]!=mid: c.close(); return jsonify(ok=False,message="This activation belongs to another PC."),409
 if not r["expires_at"]: c.close(); return jsonify(ok=False,message="License has not been activated."),409
 exp=datetime.fromisoformat(r["expires_at"].replace("Z","+00:00"))
 if exp<=datetime.now(timezone.utc): c.close(); return jsonify(ok=False,message="Activation has expired."),403
 c.close(); return jsonify(ok=True,license_id=r["id"],expires_at=r["expires_at"])

@app.post("/admin/create")
def create():
 if request.headers.get("X-Admin-Token")!=TOKEN:return jsonify(ok=False,message="Unauthorized."),401
 d=request.get_json(silent=True) or {};n=int(d.get("months",3))
 if n not in (3,6,12):return jsonify(ok=False,message="Allowed terms: 3, 6, 12 months."),400
 k=mk();c=db();c.execute("INSERT INTO licenses(key_hash,product,months,created_at) VALUES(?,?,?,?)",(h(k),str(d.get("product","AI-CAMERA-STUDIO")),n,datetime.now(timezone.utc).isoformat().replace("+00:00","Z")));c.commit();c.close();return jsonify(ok=True,key=k,months=n)
if __name__=="__main__":db();app.run(host="0.0.0.0",port=int(os.environ.get("PORT",8000)))
