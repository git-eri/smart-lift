var client_id = Date.now();
var active_lifts = [];
var lifts = []

function show_lifts() {
    lifts_div = document.getElementsByClassName("lifts")[0];
    lifts_div.innerHTML = '';
    for (var lift in lifts) {
        lift_div = document.createElement("div");
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

// Startup 
function startup() {
    ws = new WebSocket(`wss://${document.location.hostname}:8000/ws/con-sim${client_id}`);
    // Get the lift id range from uri
    var ids = document.location.href.split('#')[1].split('-')
    for (var i = parseInt(ids[0]); i <= parseInt(ids[1]); i++) {
        lifts.push(i)
    }

    startup_obj = {
        case: "hello",
        lifts: lifts
    }
    console.log("Startup", startup_obj)
    show_lifts()
    ws.addEventListener("open", (ev) => {
        ws.send(JSON.stringify(startup_obj))
    });
    

    // Message Handling
    ws.onmessage = function(event) {
        var data = JSON.parse(event.data);
        if (data.case === "move_lift") {
            obj = {
                case: "lift_moved",
                lift_id: data.lift_id,
                direction: data.direction,
                toggle: data.toggle
            }
            if (data.toggle === 1) {
                ws.send(JSON.stringify(obj))
                activateIndicator(data.lift_id, data.direction);
                return;
            } else if (data.toggle === 0) {
                ws.send(JSON.stringify(obj))
                deactivateIndicator(data.lift_id, data.direction);
                return;
            }
            console.log("error, got no on or off", event)
            return;
        } else if (data.case === "stop") {
            console.log("Emergency stop")
        } else {
            console.log("unhandled data:", event)
            return;
        }
    }
}

// Shutdown
function shutdown() {
    lifts = []
    show_lifts()
    ws.close()
}