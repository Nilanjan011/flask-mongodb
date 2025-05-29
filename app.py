from flask import Flask, jsonify, request, send_from_directory
from pymongo import MongoClient
from bson.json_util import dumps
from bson import ObjectId
from bson.errors import InvalidId
import os
import jwt
import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Config
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
MAX_FILE_SIZE_MB = 2

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024  # Flask auto-rejects larger
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change to a strong key

os.makedirs(UPLOAD_FOLDER, exist_ok=True)



client = MongoClient("mongodb+srv://nilanjanchakraborty:WvlqTsVdUapYeSQu@cluster0.fjwixiy.mongodb.net?retryWrites=true&w=majority&appName=Cluster0")

db = client["test"]


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({"error": f"File is too large. Max size is {MAX_FILE_SIZE_MB}MB."}), 413


@app.route('/')
def home():
    return 'Hello, Flask!'

@app.route('/users')
def get_users():
    # users = collection.find({})
    # return dumps(users)  # dumps returns a JSON string
    users = list(db["users"].find({}, {'_id': 0}))  # Exclude _id if not needed
    return jsonify(users)


@app.route('/user', methods=["post"])
def add_user():
    data = request.get_json()
    data['password'] = generate_password_hash(data['password'])
    result = db['users'].insert_one(data)
    return jsonify({"message": "Data inserted", "id": str(result.inserted_id)}), 201

@app.route("/user/<user_id>")
def get_user(user_id):
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)})
        print(user, request.host_url)
        if user:
            user["_id"] = str(user["_id"])

            if 'profile_pic' in user:
                filename = os.path.basename(user['profile_pic'])
                user['profile_pic'] = request.host_url.rstrip('/') + '/uploads/' + filename

            return jsonify(user), 200

        else:
            return jsonify({"error": "User not found"}), 404
    except InvalidId:
        return jsonify({"error": "Invalid user ID format"}), 400
    
@app.route('/user/<user_id>', methods=['put'])
def update_user(user_id):
    user = db["users"].find_one({"_id": ObjectId(user_id)})
    print(user_id)
    if user:
        data = request.get_json()

        db["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": data}
        )
        return jsonify({"message": "User updated"}), 200
    else:
        return jsonify({"error": "User not found"}), 404
    

@app.route('/user/<user_id>', methods=['delete'])
def delete_user(user_id):
    user = db["users"].delete_one({"_id": ObjectId(user_id)})
    print(user_id)
    if user:
        return jsonify({"message": "User deleted"}), 200
    else:
        return jsonify({"error": "User not found"}), 404



@app.route('/upload/<user_id>', methods=['POST'])
def upload_file(user_id):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    

    db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"profile_pic": "/uploads/"+filename}}
    )

    return jsonify({"message": "file upload successfully"}), 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/login', methods=["POST"])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = db['users'].find_one({'email': email})
    if user and check_password_hash(user['password'], password):
        token_payload = {
            "user_id": str(user["_id"]),
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }
        
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'message': 'Login successful', "token": token}), 200
    return jsonify({'error': 'Invalid email or password'}), 401


# Protected Route
@app.route('/profile', methods=['GET'])
def profile():
    token = request.headers.get('Authorization')
    
    if not token:
        return jsonify({"message": "Missing token"}), 401

    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        print(decoded)
        
        user = db['users'].find_one({"_id": ObjectId(decoded["user_id"])})
        if not user:
            return jsonify({"message": "User not found"}), 404

        return jsonify({
            "email": user["email"],
            "name": user.get("name", "")
        })

    except jwt.ExpiredSignatureError:
        return jsonify({"message": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"message": "Invalid token"}), 401


if __name__ == '__main__':
    app.run(debug=True)
