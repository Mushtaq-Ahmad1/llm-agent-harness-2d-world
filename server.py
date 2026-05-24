"""
Flask server: serves the GUI and exposes the world via HTTP.
"""
from src.agent import Agent
from flask import Flask, jsonify, render_template, request
from src.levels import build_world
from src.serialize import world_to_dict, legal_actions
from src.serialize import world_to_dict, movement_actions, interaction_actions, legal_actions

app = Flask(__name__)

# Single global world for now. Fine for one-player local dev.
world = build_world()
action_log = []
agent: Agent = None                           
AGENT_MAX_STEPS = 100 
agent_turn_count = 0

def ensure_agent(model: str = "claude-sonnet-4-5"):   
    """Lazily create the agent on first use, so we don't spend money
    on an Anthropic client we never actually use."""
    global agent
    if agent is None:
        agent = Agent(model=model)
    return agent

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
    global world, action_log, agent_turn_count
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
        global agent
        world = build_world()()
        agent = None
        action_log = []
        agent_turn_count = 0
        result = {"success": True, "message": "World reset."}
    else:
        result = {"success": False, "message": f"Unknown verb: {verb}"}

    action_log.append(result["message"])
    return jsonify(current_state())

@app.route('/agent_step', methods=['POST'])
def agent_step():
    global world, action_log, agent_turn_count
    data = request.get_json() or {}
    model = data.get('model', 'claude-sonnet-4-5')
    agent_instance = ensure_agent(model)
    
    # Check the cap BEFORE stepping
    if agent_turn_count >= AGENT_MAX_STEPS:
        state = current_state()
        state['agent'] = {
            'turn': agent_turn_count,
            'done': True,
            'thought': f'Reached max steps ({AGENT_MAX_STEPS}). Agent stopped.',
            'action': None,
            'scratchpad': agent_instance.scratchpad if hasattr(agent_instance, 'scratchpad') else [],
        }
        return jsonify(state)
    
    # Take one agent step
    result = agent_instance.step(world)
    agent_turn_count += 1
    
    # Mark done if we've hit the cap OR the agent won
    if agent_turn_count >= AGENT_MAX_STEPS or world.won:
        result['done'] = True
    
    if result.get('action'):
        verb = result['action']['verb']
        args = result['action']['args']
        action_log.append(f"Agent turn {result['turn']}: {verb}({args})")
    
    state = current_state()
    state['agent'] = result
    return jsonify(state)


@app.route('/agent_reset', methods=['POST'])
def agent_reset():
    global agent, agent_turn_count
    data = request.get_json() or {}
    model = data.get('model', 'claude-sonnet-4-5')
    agent = Agent(model=model)
    agent_turn_count = 0    # NEW
    return jsonify({"ok": True, "model": model})


if __name__ == "__main__":
    app.run(debug=True, port=5000)