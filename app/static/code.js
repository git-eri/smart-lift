var client_id = Date.now();
var active_lifts = [];
var lift_status = [];
var ws = new WebSocket(`ws://${document.location.hostname}:8000/ws/cli${client_id}`);

// Lifts
function startLift(con_id, lift_id, action) {
    active_lifts.push(lift_id);
    if (active_lifts.length > 1) {
        for (active_lift in active_lifts) {
            for (i = 0; i < 3; i++) {
                ws.send("lift;" + con_id + ";" + lift_id + ";" + i + ";off");
                deactivateIndicator(active_lift, i);
            }
        }
        active_lifts = [];
        alert("Nicht mehr als eine Aktion steuerbar!");
        return;
    }
    ws.send("lift;" + con_id + ";" + lift_id + ";" + action + ";on");
}

function endLift(con_id, lift_id, action) {
    if (active_lifts.includes(lift_id)) {
        ws.send("lift;" + con_id + ";" + lift_id + ";" + action + ";off");
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

function liftStatusChange(lifts) {
    // Has the number of lifts changed?
    if (lift_status === lifts) {
        return;
    }
    var lift_status = lifts;
    var lift_status_json = JSON.parse(lift_status);
    var lifts_div = document.getElementsByClassName("lifts")[0];
    lifts_div.innerHTML = '';
    console.log(lift_status_json);
    // Sort lifts by id
    lift_status_json.sort(function(a, b) {
        return a.id - b.id;
    });
    console.log("Sorted lifts:", lift_status_json)
    for (var i = 0; i < lift_status_json.length; i++) {
        var lift_div = document.createElement("div");
        lift_div.className = "lift";
        lifts_div.appendChild(lift_div);
        h1 = document.createElement("h1");
        h1.innerHTML = lift_status_json[i].name;
        lift_div.appendChild(h1);
        table = document.createElement("table");
        table.className = "table";
        lift_div.appendChild(table);
        for (var j = 0; j < 3; j++) {
            button_div = document.createElement("div");
            button_div.className = "buttons";
            button_div.id = `button${lift_status_json[i].id}-${j}`;
            table.appendChild(button_div);
            button_container = document.createElement("div");
            button_container.className = "button-container";
            button_div.appendChild(button_container);
            button = document.createElement("button");
            button.className = "button";
            button.innerHTML = ["Up", "Down", "Lock"][j];
            button.setAttribute(
                "onpointerdown",
                `startLift("${lift_status_json[i].controller}", "${lift_status_json[i].id}", "${j}");`
            );
            button.setAttribute(
                "onpointerleave",
                `endLift("${lift_status_json[i].controller}", "${lift_status_json[i].id}", "${j}");`
            );
            button.setAttribute(
                "onpointerup",
                `endLift("${lift_status_json[i].controller}", "${lift_status_json[i].id}", "${j}");`
            );
            button_container.appendChild(button);
            indicator = document.createElement("div");
            indicator.className = "indicator";
            indicator.id = `indicator${lift_status_json[i].id}-${j}`;
            button_div.appendChild(indicator);
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
    var data = event.data.split(";");
    if (data[0] === "moved_lift") {
        lift_id = data[1];
        action = data[2];
        on_off = data[3];
        if (on_off === "on") {
            activateIndicator(lift_id, action);
            return;
        } else if (on_off === "off") {
            deactivateIndicator(lift_id, action);
            return;
        }
        console.log("error, got no on or off", event)
        return;
    } else if (data[0] === "stop") {
        console.log("EMERGENCY STOP")
    } else if (data[0] === "lift_status") {
        liftStatusChange(event.data.split(";")[1]);
        return;
    } else if (data[0] === "msg") {
        return;
    } else {
        console.log("unhandled data:", event)
        return;
    }
    return;
}