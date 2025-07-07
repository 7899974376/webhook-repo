
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime  #handles date/time
from zoneinfo import ZoneInfo  # lets we Asia/Kolkata timezone for timestamp
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize Flask
app = Flask(__name__)
CORS(app)

# MongoDB setup
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017") #Connects to MongoDB
client = MongoClient(MONGO_URI) 
db = client["events"]   #DB name is events
collection = db["events"]  #Collection name is events

# homepage routes or visiting
@app.route("/")
def home():
    return render_template("index.html")

#Webhook Receiver
#This is the main webhook endpoint that GitHub will POST to.
@app.route("/webhook", methods=["POST"])
def webhook():
    event_type = request.headers.get("X-GitHub-Event")
    data = request.json

    # Current time in IST
    ist_zone = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist_zone)
    iso_timestamp = now_ist.isoformat()
    readable_timestamp = now_ist.strftime("%d %b %Y, %H:%M:%S")  # e.g., 06 Jul 2025, 13:35:45

    # Base event structure
    event = {
        "timestamp": iso_timestamp,
        "timestamp_human": readable_timestamp
    }
   
    #Handle Push Events:
    if event_type == "push":
        event.update({
            "action": "PUSH",
            "author": data.get("pusher", {}).get("name"),
            "to_branch": data.get("ref", "").split("/")[-1],
            "request_id": data.get("after")
        })
    #Handle Pull Request / Merge Events:
    elif event_type == "pull_request":       
        pr = data.get("pull_request", {})
        action = data.get("action")
        pr_id = str(pr.get("id"))
        
        # Pull Request Opened
        if action == "opened":
            event.update({
                "action": "PULL_REQUEST",
                "author": pr.get("user", {}).get("login"),
                "from_branch": pr.get("head", {}).get("ref"),
                "to_branch": pr.get("base", {}).get("ref"),
                "request_id": pr_id
            })
        #Pull Request Merged OR closed
        elif action == "closed" and pr.get("merged"):
            event.update({
                "action": "MERGE",
                "author": pr.get("user", {}).get("login"),
                "from_branch": pr.get("head", {}).get("ref"),
                "to_branch": pr.get("base", {}).get("ref"),
                "request_id": pr_id
            })
        else:
            return jsonify({"status": "ignored"}), 200  #Ignore Unknown Events
    else:
        return jsonify({"status": "ignored"}), 200

    # Save to MongoDB
    collection.insert_one(event)
    return jsonify({"status": "stored"}), 201
  
#frontend to fetch the latest events.
@app.route("/events", methods=["GET"])
def get_events():
    # Include human-readable timestamp
    events = list(collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(10))
    return jsonify(events)

#Runs the app
if __name__ == "__main__":
    app.run(debug=True)
