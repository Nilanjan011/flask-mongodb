from flask import Flask, jsonify, request, send_from_directory, render_template
from pymongo import MongoClient
from bson.json_util import dumps
from bson import ObjectId
from bson.errors import InvalidId
import os
import jwt
import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_mail import Mail, Message
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


# Configure Flask-Mail (example: Gmail SMTP)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nilanjan.chakraborty@codeclouds.in'
app.config['MAIL_PASSWORD'] = 'ykmzonytmyhxoyyg'
app.config['MAIL_DEFAULT_SENDER'] = 'no-reply@gmail.com'

mail = Mail(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({"error": f"File is too large. Max size is {MAX_FILE_SIZE_MB}MB."}), 413

@app.context_processor
def inject_navbar():
    navbar_items = ['Home', 'Products', 'Services', 'Contact']
    return dict(navbar_items=navbar_items)


@app.route('/')
def home():
    users = list(db["users"].find({}, {'_id': 0}))  # Exclude _id if not needed
    return render_template('page/index.html', users=users)

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


# middleware
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({"message": "Token is missing"}), 401

        try:
            decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user_id = decoded['user_id']  # attach to request context
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated

# Protected Route
@app.route('/profile', methods=['GET'])
@token_required
def profile():
    print(request.user_id)

    try:
        user = db['users'].find_one({"_id": ObjectId(request.user_id)})
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


@app.route('/post')
def post():
    # users = db["users"].find({})
    # for user in users:
    #     print(user)
    #     db.posts.insert_one({
    #         "user_id": ObjectId(user['_id']),
    #         "title": user['name'] + "title",
    #         "desc": user['name'] + "desc"
    #     })

    # return ''

    # join users and posts
    # u = db.users.find({
    #     "$or": [
    #         { "is_active": "1" },
    #         { "is_delete": "0" }
    #     ]
    # })
    # return dumps(u)
    # users = db.users.aggregate([
    #     {
    #         "$match": {
    #             "$or": [
    #                 { "is_active": "1" },
    #                 { "is_delete": "0" }
    #             ]
    #         }
    #     },
    #     {
    #         "$lookup": {
    #             "from": "posts",
    #             "localField": "_id",
    #             "foreignField": "user_id",
    #             "as": "post"
    #         }
    #     },
    #     {
    #         "$unwind": {
    #             "path":"$post",
    #             "preserveNullAndEmptyArrays":True # 👈 keeps users even if they have no posts
    #         }
    #     },
    #     {
    #         "$match": {
    #             "post.is_active": "1"  # only active posts
    #         }
    #     }
    # ])


    ## post come should be array under of user and all users data come but only matching post will come
#     users = db.users.aggregate([
#     {
#         "$match": {
#             "$or": [
#                 { "is_active": "1" },
#                 { "is_delete": "0" }
#             ]
#         }
#     },
#     {
#         "$lookup": {
#             "from": "posts",
#             "let": { "userId": "$_id" },
#             "pipeline": [
#                 {
#                     "$match": {
#                         "$expr": {
#                             "$and": [
#                                 { "$eq": ["$user_id", "$$userId"] },
#                                 { "$eq": ["$is_active", "1"] }
#                             ]
#                         }
#                     }
#                 }
#             ],
#             "as": "post"
#         }
#     }
# ])

    users = db.users.aggregate([
        {
            "$lookup": {
                "from": "user_images",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "images"
            }
        },
        {
            "$addFields": {
                "image_count": { "$size": "$images" }
            }
        },
        {
            "$sort":{
                "image_count":-1
            }
        },
        {
            "$project": {
                "name": 1,
                "email": 1,
                "image_count": 1
            }
        }
    ])

    return dumps(users)

@app.route('/send-welcome-mail')
def send_welcome_mail():
    recipient = "nilanjan.chakraborty@codeclouds.in"
    name = "Nilanjan Chakraborty"
    # return render_template('email/welcome.html', name=name)

    msg = Message(
        subject='Welcome to Flask App!',
        recipients=[recipient],
        html = render_template('email/welcome.html', name=name)
    )

    try:
        mail.send(msg)
        return jsonify({'message': 'Welcome email sent successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    


if __name__ == '__main__':
    app.run(debug=True)
