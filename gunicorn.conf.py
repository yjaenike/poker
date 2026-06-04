workers = 1
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
worker_connections = 100
bind = "0.0.0.0:" + __import__("os").environ.get("PORT", "8080")
