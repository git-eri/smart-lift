var active_lifts = [];
var lifts = [];
var client_id = "cli-" + Date.now();
var ws;

function startup() {
    if (ws && ws.readyState !== WebSocket.CLOSED) {
        return; // Already connected
    }
    ws = new WebSocket(`wss://${document.location.host}/ws/${client_id}`);
    ws.onopen = function (event) {
        console.log("Connection established");
    };
    // Message Handling
    ws.onmessage = function(event) {
        data = JSON.parse(event.data);
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
}

function disconnect() {
    ws.close();
    console.log("Connection closed");
    return;
}

// Lifts
function startLift(con_id, lift_id, direction) {
    active_lifts.push(lift_id);
    if (active_lifts.length > 1) {
        for (const active_lift of active_lifts) {
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
        message = {
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
    indicator = document.getElementById(`indicator${liftId}-${buttonId}`);
    indicator.classList.add('active');
    return;
}

function deactivateIndicator(liftId, buttonId) {
    indicator = document.getElementById(`indicator${liftId}-${buttonId}`);
    indicator.classList.remove('active');
    return;
}

function liftStatusChange(lifts_new) {
    lifts_div = document.getElementsByClassName("lifts")[0];
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
            lift_div = document.createElement("div");
            lift_div.className = "lift";
            lifts_div.appendChild(lift_div);
            h1 = document.createElement("h1");
            h1.textContent = lifts[con_id][i].name;
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

(function() {
    var hidden = "hidden";
  
    // Standards:
    if (hidden in document)
      document.addEventListener("visibilitychange", onchange);
    else if ((hidden = "mozHidden") in document)
      document.addEventListener("mozvisibilitychange", onchange);
    else if ((hidden = "webkitHidden") in document)
      document.addEventListener("webkitvisibilitychange", onchange);
    else if ((hidden = "msHidden") in document)
      document.addEventListener("msvisibilitychange", onchange);
    // IE 9 and lower:
    else if ("onfocusin" in document)
      document.onfocusin = document.onfocusout = onchange;
    // All others:
    else
      window.onpageshow = window.onpagehide
      = window.onfocus = window.onblur = onchange;
  
    function onchange (evt) {
      var v = "visible", h = "hidden",
          evtMap = {
            focus:v, focusin:v, pageshow:v, blur:h, focusout:h, pagehide:h
          };
  
      evt = evt || window.event;
      if (evt.type in evtMap)
        if (evtMap[evt.type] === "visible")
          startup()
        else
          disconnect()
      else
        if (this[hidden])
          disconnect()
        else
          startup()
    }
  
    // set the initial state (but only if browser supports the Page Visibility API)
    if( document[hidden] !== undefined )
      onchange({type: document[hidden] ? "blur" : "focus"});
  })();