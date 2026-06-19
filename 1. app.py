1. app.py 

from flask import Flask, render_template, request, redirect, session, url_for
import boto3
import uuid
import pymysql
from flask_session import Session
import hmac
import hashlib
import base64

app = Flask(__name__)
app.secret_key = "secure-cloud-drive-secret-key-2026"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

BUCKET_NAME = "secure-cloud-storage-zranofi"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "jpg", "jpeg", "png"}

AWS_REGION = "us-east-1"
COGNITO_USER_POOL_ID = "us-east-1_rx3xAtGQq"
COGNITO_CLIENT_ID = "2rk765tcpb6ev7hpf18vf7grh4"
COGNITO_CLIENT_SECRET = "c62g4b4ao8h6sb84hf41p79l5rluvepb9elkp97j3aponhjbhi7"

s3 = boto3.client("s3", region_name=AWS_REGION)
cognito = boto3.client("cognito-idp", region_name=AWS_REGION)

DB_CONFIG = {
    "host": "secure-cloud-drive-db.csuwiuoyz36c.us-east-1.rds.amazonaws.com",
    "user": "admin",
    "password": "CloudDrive123!",
    "database": "cloud_drive",
    "port": 3306
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_secret_hash(username):
    message = username + COGNITO_CLIENT_ID
    dig = hmac.new(
        COGNITO_CLIENT_SECRET.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            response = cognito.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password,
                    "SECRET_HASH": get_secret_hash(username)
                },
                ClientId=COGNITO_CLIENT_ID
            )

            print("COGNITO RESPONSE =", response)

            if "AuthenticationResult" not in response:
                error = f"COGNITO RESPONSE = {response}"
                return render_template("login.html", error=error)

            session["username"] = username
            session["token"] = response["AuthenticationResult"]["AccessToken"]

            return redirect(url_for("index"))
        except cognito.exceptions.NotAuthorizedException:
            error = "Username atau password salah!"
        except cognito.exceptions.UserNotFoundException:
            error = "Pengguna tidak ditemukan!"
        except Exception as e:
            error = f"Error: {str(e)}"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        try:
            cognito.sign_up(
                ClientId=COGNITO_CLIENT_ID,
                SecretHash=get_secret_hash(username),
                Username=username,
                Password=password,
                UserAttributes=[{"Name": "email", "Value": email}]
            )
            cognito.admin_confirm_sign_up(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=username
            )
            success = "Registrasi berhasil! Silakan login."
        except cognito.exceptions.UsernameExistsException:
            error = "Username sudah digunakan!"
        except Exception as e:
            error = f"Error: {str(e)}"
    return render_template("register.html", error=error, success=success)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, s3_key, upload_date FROM files ORDER BY upload_date DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    files = []
    for row in rows:
        files.append({
            "id": row[0],
            "filename": row[1],
            "s3_key": row[2],
            "upload_date": row[3]
        })
    return render_template("index.html", files=files, username=session.get("username"))

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return redirect("/")
    file = request.files["file"]
    if file.filename == "":
        return redirect("/")
    if file and allowed_file(file.filename):
        original_name = file.filename
        ext = file.filename.rsplit(".", 1)[1].lower()
        new_filename = str(uuid.uuid4()) + "." + ext
        s3.upload_fileobj(file, BUCKET_NAME, new_filename)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (filename, s3_key) VALUES (%s, %s)",
            (original_name, new_filename)
        )
        conn.commit()
        cursor.close()
        conn.close()
    return redirect("/")

@app.route("/delete/<int:file_id>")
@login_required
def delete(file_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT s3_key FROM files WHERE id = %s", (file_id,))
    result = cursor.fetchone()
    if result:
        s3_key = result[0]
        s3.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
        conn.commit()
    cursor.close()
    conn.close()
    return redirect("/")

@app.route("/download/<int:file_id>")
@login_required
def download(file_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT s3_key FROM files WHERE id = %s", (file_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        s3_key = result[0]
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=300
        )
        return redirect(url)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
