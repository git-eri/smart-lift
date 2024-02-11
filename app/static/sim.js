var client_id = Date.now();
var ws = new WebSocket(`ws://${document.location.hostname}:8000/ws/con-sim${client_id}`);
var active_lifts = [];
var lifts = []

// Get the lift id range from uri
var ids = document.location.href.split('#')[1].split('-')
for (var i = parseInt(ids[0]); i <= parseInt(ids[1]); i++) {
    lifts.push(i)
}

// Startup 
function startup() {
    if (ws.readyState === 3) {
        ws = new WebSocket(`ws://${document.location.hostname}:8000/ws/con-sim${Date.now()}`);

    }
    startup_obj = {
        message: "hello",
        lifts: lifts
    }
    show_lifts()
    ws.send(JSON.stringify(startup_obj))
}

// Shutdown
function shutdown() {
    lifts = []
    show_lifts()
    ws.close()
}

function show_lifts() {
    var lifts_div = document.getElementsByClassName("lifts")[0];
    lifts_div.innerHTML = '';
    for (var lift in lifts) {
        var lift_div = document.createElement("div");
        lift_div.className = "lift";
        lifts_div.appendChild(lift_div);
        h1 = document.createElement("h1");
        h1.innerHTML = lifts[lift];
        lift_div.appendChild(h1);
        table = document.createElement("table");
        table.className = "table";
        lift_div.appendChild(table);
        for (var j = 0; j < 3; j++) {
            button_div = document.createElement("div");
            button_div.className = "buttons";
            button_div.id = `button${lifts[lift].id}-${j}`;
            table.appendChild(button_div);
            button_container = document.createElement("div");
            button_container.className = "button-container";
            button_div.appendChild(button_container);
            button = document.createElement("button");
            button.className = "button";
            button.innerHTML = ["Up", "Down", "Lock"][j];
            button_container.appendChild(button);
            indicator = document.createElement("div");
            indicator.className = "indicator";
            indicator.id = `indicator${lifts[lift]}-${j}`;
            button_div.appendChild(indicator);
        }
    }
}

// Indicators
function activateIndicator(liftId, buttonId) {
    var indicator = document.getElementById(`indicator${liftId}-${buttonId}`);
    indicator.classList.add('active');
    return;
}

function deactivateIndicator(liftId, buttonId) {
    var indicator = document.getElementById(`indicator${liftId}-${buttonId}`);
    indicator.classList.remove('active');
    return;
}

// Message Handling
ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    if (data.message === "lift") {
        lift_id = data.lift.id;
        action = data.lift.action;
        on_off = data.lift.on_off;
        obj = {
            message: "moved_lift",
            lift: {
                id: lift_id,
                action: action,
                on_off: on_off,
                status: 0
            }
        }
        if (on_off === 1) {
            ws.send(JSON.stringify(obj))
            activateIndicator(lift_id, action);
            return;
        } else if (on_off === 0) {
            ws.send(JSON.stringify(obj))
            deactivateIndicator(lift_id, action);
            return;
        }
        console.log("error, got no on or off", event)
        return;
    } else {
        console.log("unhandled data:", event)
        return;
    }
}