// Cell rendering size — tweak to fit canvas
const CELL = 48;

const canvas = document.getElementById('grid');
const ctx = canvas.getContext('2d');

const colors = {
    FLOOR: '#1f1f3a',
    WALL: '#3a3a5a',
    DOOR_LOCKED: '#7a3a3a',
    DOOR_OPEN: '#3a7a3a',
    EXIT: '#3a7a3a',
};

async function fetchState() {
    const res = await fetch('/state');
    return res.json();
}

async function doAction(verb, args) {
    const res = await fetch('/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({verb, args}),
    });
    const state = await res.json();
    render(state);
}

function render(state) {
    const {world, legal_actions, log} = state;

    // Resize canvas to fit
    canvas.width = world.width * CELL;
    canvas.height = world.height * CELL;

    // Draw cells
    for (let y = 0; y < world.height; y++) {
        for (let x = 0; x < world.width; x++) {
            const cell = world.cells[y][x];
            ctx.fillStyle = colors[cell.terrain] || '#000';
            ctx.fillRect(x * CELL, y * CELL, CELL, CELL);
            ctx.strokeStyle = '#0a0a18';
            ctx.strokeRect(x * CELL, y * CELL, CELL, CELL);

            // Draw objects
            for (const obj of cell.objects) {
                if (obj.type === 'lever') {
                    ctx.fillStyle = obj.is_up ? '#f0c060' : '#806030';
                    ctx.fillRect(x * CELL + 18, y * CELL + 12, 12, 24);
                    ctx.fillStyle = '#fff';
                    ctx.font = '10px monospace';
                    ctx.fillText(obj.id.replace('lever_', ''), x * CELL + 20, y * CELL + 44);
                } else if (obj.type === 'note') {
                    ctx.fillStyle = '#f0e0a0';
                    ctx.fillRect(x * CELL + 14, y * CELL + 14, 20, 20);
                    ctx.fillStyle = '#000';
                    ctx.font = 'bold 14px monospace';
                    ctx.fillText('?', x * CELL + 19, y * CELL + 28);
                }
            }
        }
    }

    // Draw agent
    const [ax, ay] = world.agent_pos;
    ctx.fillStyle = '#60c0f0';
    ctx.beginPath();
    ctx.arc(ax * CELL + CELL / 2, ay * CELL + CELL / 2, CELL / 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Status
    document.getElementById('status').textContent =
        `Position: (${ax}, ${ay})  |  Inventory: ${world.inventory.length ? world.inventory.join(', ') : 'empty'}  |  ${world.won ? '🎉 WON' : 'Playing'}`;

    // Action buttons
    const actionsDiv = document.getElementById('actions');
    actionsDiv.innerHTML = '';
    for (const action of legal_actions) {
        const btn = document.createElement('button');
        btn.textContent = action.label;
        btn.onclick = () => doAction(action.verb, action.args);
        actionsDiv.appendChild(btn);
    }

    // Log
    const logDiv = document.getElementById('log');
    logDiv.innerHTML = '';
    for (const line of log) {
        const div = document.createElement('div');
        div.textContent = line;
        logDiv.appendChild(div);
    }
    logDiv.scrollTop = logDiv.scrollHeight;
}

document.getElementById('reset').onclick = () => doAction('reset', []);

// Initial load
fetchState().then(render);