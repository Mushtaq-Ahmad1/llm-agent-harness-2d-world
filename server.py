"""
Flask server: serves the GUI and exposes the world via HTTP.
"""
from flask import Flask, jsonify, render_template, request
from src.levels import build_level_1
from src.serialize import world_to_dict, legal_actions
from src.serialize import world_to_dict, movement_actions, interaction_actions, legal_actions



app = Flask(__name__)

# Single global world for now. Fine for one-player local dev.
world = build_level_1()
action_log = []

def current_state():
    return {
        "world": world_to_dict(world),
        "movement_actions": movement_actions(world),
        "interaction_actions": interaction_actions(world),
        "legal_actions": legal_actions(world),
        "log": action_log[-10:],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/state")
def state():
    return jsonify(current_state())


@app.route("/action", methods=["POST"])
def action():
    global world, action_log
    data = request.get_json()
    verb = data.get("verb")
    args = data.get("args", [])

    if verb == "move":
        result = world.move(args[0])
    elif verb == "flip":
        result = world.flip_lever(args[0])
    elif verb == "read":
        result = world.read(args[0])
    elif verb == "pick_up":
        result = world.pick_up(args[0])
    elif verb == "drop":
        result = world.drop(args[0])
    elif verb == "inspect":
        result = world.inspect(args[0])
    elif verb == "reset":
        world = build_level_1()
        action_log = []
        result = {"success": True, "message": "World reset."}
    else:
        result = {"success": False, "message": f"Unknown verb: {verb}"}

    action_log.append(result["message"])
    return jsonify(current_state())


if __name__ == "__main__":
    app.run(debug=True, port=5000)