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
    PRESSURE_PLATE: '#1f1f3a'
};

const plateColors = {
    red: '#a04040',
    green: '#40a060',
    blue: '#4060a0',
    yellow: '#c0a040'
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
    const {world, log} = state;

    // Resize canvas to fit
    canvas.width = world.width * CELL;
    canvas.height = world.height * CELL;

    // Draw cells
    for (let y = 0; y < world.height; y++) {
        for (let x = 0; x < world.width; x++) {
            const cell = world.cells[y][x];
            ctx.fillStyle = colors[cell.terrain] || '#000';
            ctx.fillRect(x * CELL, y * CELL, CELL, CELL);

            // Tint pressure plates by color
            if (cell.terrain === 'PRESSURE_PLATE' && cell.plate_color) {
                ctx.fillStyle = plateColors[cell.plate_color] || '#888';
                ctx.fillRect(x * CELL + 6, y * CELL + 6, CELL - 12, CELL - 12);
            }

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
                } else if (obj.type === 'box') {
                    // Default brown wood color
                    let fill = '#a07050';
                    let stroke = '#604030';
                    // Once inspected, color it to hint at its label
                    if (obj.label_revealed && obj.label) {
                        const labelToColor = {A: '#a04040', B: '#40a060', C: '#4060a0'};
                        fill = labelToColor[obj.label] || fill;
                        stroke = '#fff';
                    }
                    ctx.fillStyle = fill;
                    ctx.fillRect(x * CELL + 8, y * CELL + 8, CELL - 16, CELL - 16);
                    ctx.strokeStyle = stroke;
                    ctx.lineWidth = 2;
                    ctx.strokeRect(x * CELL + 8, y * CELL + 8, CELL - 16, CELL - 16);
                    ctx.fillStyle = '#fff';
                    ctx.font = '10px monospace';
                    const tag = obj.label_revealed ? obj.label : obj.id.replace('box_', 'B');
                    ctx.fillText(tag, x * CELL + 20, y * CELL + 30);
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
    const inventoryText = world.inventory.length
        ? world.inventory.map(o => o.id).join(', ')
        : 'empty';
    document.getElementById('status').textContent =
        `Position: (${ax}, ${ay})  |  Inventory: ${inventoryText}  |  ${world.won ? '🎉 WON' : 'Playing'}`;

    // Action buttons
    // Movement buttons — always rendered, dimmed if illegal
    const moveDiv = document.getElementById('movement-actions');
    moveDiv.innerHTML = '';
    for (const action of state.movement_actions) {
        const btn = document.createElement('button');
        btn.textContent = action.label;
        btn.disabled = !action.legal;
        btn.onclick = () => doAction(action.verb, action.args);
        moveDiv.appendChild(btn);
    }

    // Interaction buttons — only rendered when available
    const interactionDiv = document.getElementById('interaction-actions');
    interactionDiv.innerHTML = '';
    for (const action of state.interaction_actions) {
        const btn = document.createElement('button');
        btn.textContent = action.label;
        btn.onclick = () => doAction(action.verb, action.args);
        interactionDiv.appendChild(btn);
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