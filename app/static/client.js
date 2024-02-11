var active_lifts = [];
var lifts = [];
var client_id = "cli" + Date.now();

var ws = new WebSocket(`ws://${document.location.hostname}:8000/ws/${client_id}`);

// Lifts
function startLift(con_id, lift_id, direction) {
    active_lifts.push(lift_id);
    if (active_lifts.length > 1) {
        for (active_lift in active_lifts) {
            for (i = 0; i < 3; i++) {
                var message = {
                    case: "move_lift",
                    con_id: con_id,
                    client_id: client_id,
                    lift_id: lift_id,
                    direction: direction,
                    toggle: 0
                };
                ws.send(JSON.stringify(message));
                deactivateIndicator(active_lift, i);
            }
        }
        active_lifts = [];
        alert("Nicht mehr als eine Aktion steuerbar!");
        return;
    }
    var message = {
        case: "move_lift",
        con_id: con_id,
        client_id: client_id,
        lift_id: lift_id,
        direction: direction,
        toggle: 1
    };
    ws.send(JSON.stringify(message));
}

function endLift(con_id, lift_id, direction) {
    if (active_lifts.includes(lift_id)) {
        var message = {
            case: "move_lift",
            con_id: con_id,
            client_id: client_id,
            lift_id: lift_id,
            direction: direction,
            toggle: 0
        };
        ws.send(JSON.stringify(message));
        active_lifts.splice(active_lifts.indexOf(lift_id), 1);
        return;
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

function liftStatusChange(lifts_new) {
    var lifts_div = document.getElementsByClassName("lifts")[0];
    lifts_div.innerHTML = '';
    // Has the number of lifts changed?
    if (lifts === lifts_new) {
        console.log("lift status unchanged");
        return;
    }
    lifts = lifts_new;
    lifts = JSON.parse(JSON.stringify(lifts));
    for (var con_id in lifts) {
        for (var i in lifts[con_id]) {
            var lift_div = document.createElement("div");
            lift_div.className = "lift";
            lifts_div.appendChild(lift_div);
            h1 = document.createElement("h1");
            h1.innerHTML = lifts[con_id][i].name;
            lift_div.appendChild(h1);
            table = document.createElement("table");
            table.className = "table";
            lift_div.appendChild(table);
            for (var j = 0; j < 3; j++) {
                button_div = document.createElement("div");
                button_div.className = "buttons";
                button_div.id = `button${lifts[con_id][i].id}-${j}`;
                table.appendChild(button_div);
                button_container = document.createElement("div");
                button_container.className = "button-container";
                button_div.appendChild(button_container);
                button = document.createElement("button");
                button.className = "button";
                button.innerHTML = ["Up", "Down", "Lock"][j];
                button.setAttribute(
                    "onpointerdown",
                    `startLift("${con_id}", "${lifts[con_id][i].id}", "${j}");`
                );
                button.setAttribute(
                    "onpointerleave",
                    `endLift("${con_id}", "${lifts[con_id][i].id}", "${j}");`
                );
                button.setAttribute(
                    "onpointerup",
                    `endLift("${con_id}", "${lifts[con_id][i].id}", "${j}");`
                );
                button_container.appendChild(button);
                indicator = document.createElement("div");
                indicator.className = "indicator";
                indicator.id = `indicator${lifts[con_id][i].id}-${j}`;
                button_div.appendChild(indicator);
            }
        }
    }
    return;
}

// Emergency Stop
function emergencyStop() {
    ws.send("stop")
    return;
}

// Message Handling
ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    console.log(data);
    if (data.case === "lift_moved") {
        if (data.toggle === 1) {
            activateIndicator(data.lift_id, data.direction);
            return;
        } else if (data.toggle === 0) {
            deactivateIndicator(data.lift_id, data.direction);
            return;
        }
        console.log("error, got no on or off", event)
        return;

    } else if (data.case === "stop") {
        alert("EMERGENCY STOP")

    } else if (data.case === "online_lifts") {
        liftStatusChange(data.lifts);
        return;

    } else if (data.case === "info") {
        return;

    } else {
        console.log("unhandled data:", event)
        return;
    }
    return;
}