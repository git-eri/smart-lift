var active_lifts = [];
var lifts = [];
var ws = new WebSocket(`ws://${document.location.hostname}:8000/ws/cli${Date.now()}`);

// Lifts
function startLift(con_id, lift_id, action) {
    active_lifts.push(lift_id);
    if (active_lifts.length > 1) {
        for (active_lift in active_lifts) {
            for (i = 0; i < 3; i++) {
                var obj = {
                    message: "lift",
                    lift: {
                        con_id: con_id,
                        id: lift_id,
                        action: action,
                        on_off: 0
                    }
                };
                ws.send(JSON.stringify(obj));
                deactivateIndicator(active_lift, i);
            }
        }
        active_lifts = [];
        alert("Nicht mehr als eine Aktion steuerbar!");
        return;
    }
    var obj = {
        message: "lift",
        lift: {
            con_id: con_id,
            id: lift_id,
            action: action,
            on_off: 1
        }
    };
    ws.send(JSON.stringify(obj));
}

function endLift(con_id, lift_id, action) {
    if (active_lifts.includes(lift_id)) {
        var obj = {
            message: "lift",
            lift: {
                con_id: con_id,
                id: lift_id,
                action: action,  // Beachte, dass "action" statt "i" verwendet werden sollte.
                on_off: 0
            }
        };
        ws.send(JSON.stringify(obj));
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
    console.log(lifts)
    // Sort lifts by id
    //Object.values(lifts).sort((a,b) => a.count - b.count)
    console.log("Sorted lifts:", lifts)
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
    if (data.message === "moved_lift") {
        lift_id = data.lift.id;
        action = data.lift.action;
        on_off = data.lift.on_off;
        if (on_off === "1") {
            activateIndicator(lift_id, action);
            return;
        } else if (on_off === "0") {
            deactivateIndicator(lift_id, action);
            return;
        }
        console.log("error, got no on or off", event)
        return;
    } else if (data.message === "stop") {
        console.log("EMERGENCY STOP")
    } else if (data.message === "lift_status") {
        liftStatusChange(data.lifts);
        return;
    } else if (data.message === "info") {
        return;
    } else {
        console.log("unhandled data:", event)
        return;
    }
    return;
}