import os,requests,getpass
u=os.environ.get("ACTIVATION_SERVER_URL") or input("Server URL: ").strip().rstrip("/")
t=os.environ.get("ACTIVATION_ADMIN_TOKEN") or getpass.getpass("Admin token: ")
n=int(input("Months (3/6/12): ") or "3")
print(requests.post(u+"/admin/create",json={"months":n},headers={"X-Admin-Token":t},timeout=15).text)
