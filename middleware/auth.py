from functools import wraps
from flask import request, jsonify, current_app
import jwt

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        # print(current_app.config['SECRET_KEY'], token)

        if not token:
            return jsonify({"message": "Token is missing"}), 401

        try:
            # Remove Bearer prefix if present
            if token.startswith("Bearer "):
                token = token.split(" ")[1]

            decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user_id = decoded.get('user_id')

        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated
