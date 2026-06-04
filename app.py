import os
from flask import Flask, redirect
from flask_socketio import SocketIO
from poker import poker_bp, init_poker_socketio

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

app.register_blueprint(poker_bp)
socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")
init_poker_socketio(socketio)


@app.route("/")
def root():
    return redirect("/poker")


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5002, debug=True)
