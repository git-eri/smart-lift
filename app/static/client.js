let activeLifts = [];
let lifts = [];
const clientId = "cli-" + Date.now();
let ws;

function startup() {
    ws = new WebSocket(`wss://${location.host}/ws/${clientId}`);

    ws.addEventListener("open", () => console.log("Connection established"));

    ws.addEventListener("message", (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error("Invalid JSON received:", event.data);
            return;
        }

        switch (data.case) {
            case "lift_moved":
                if (data.toggle === 1) activateIndicator(data.lift_id, data.direction);
                else if (data.toggle === 0) deactivateIndicator(data.lift_id, data.direction);
                else console.warn("Invalid toggle value:", data);
                break;

            case "stop":
                alert("EMERGENCY STOP");
                break;

            case "online_lifts":
                updateLifts(data.lifts);
                break;

            case "info":
                break;

            default:
                console.warn("Unhandled message:", data);
        }
    });

    ws.addEventListener("close", () => console.log("Connection closed"));
}

function disconnect() {
    if (ws) ws.close();
}

function startLift(conId, liftId, direction) {
    if (!activeLifts.includes(liftId)) activeLifts.push(liftId);

    if (activeLifts.length > 1) {
        activeLifts.forEach(id => {
            for (let i = 0; i < 3; i++) {
                sendLiftMessage(conId, id, i, 0);
                deactivateIndicator(id, i);
            }
        });
        activeLifts = [];
        alert("Nicht mehr als eine Aktion steuerbar!");
        return;
    }

    sendLiftMessage(conId, liftId, direction, 1);
}

function endLift(conId, liftId, direction) {
    if (activeLifts.includes(liftId)) {
        sendLiftMessage(conId, liftId, direction, 0);
        activeLifts = activeLifts.filter(id => id !== liftId);
    }
}

function sendLiftMessage(conId, liftId, direction, toggle) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
        case: "move_lift",
        con_id: conId,
        client_id: clientId,
        lift_id: liftId,
        direction,
        toggle
    }));
}

function activateIndicator(liftId, dir) {
    const indicator = document.getElementById(`indicator${liftId}-${dir}`);
    if (indicator) indicator.classList.add("active");
}

function deactivateIndicator(liftId, dir) {
    const indicator = document.getElementById(`indicator${liftId}-${dir}`);
    if (indicator) indicator.classList.remove("active");
}

function updateLifts(newLifts) {
    if (JSON.stringify(lifts) === JSON.stringify(newLifts)) return;

    lifts = JSON.parse(JSON.stringify(newLifts));
    const liftsDiv = document.querySelector(".lifts");
    liftsDiv.innerHTML = '';

    for (const [conId, group] of Object.entries(lifts)) {
        for (const lift of group) {
            const liftDiv = document.createElement("div");
            liftDiv.className = "lift";

            const title = document.createElement("h1");
            title.textContent = lift.name;
            liftDiv.appendChild(title);

            const table = document.createElement("table");
            table.className = "table";
            liftDiv.appendChild(table);

            ["Up", "Down", "Lock"].forEach((label, dir) => {
                const buttonDiv = document.createElement("div");
                buttonDiv.className = "buttons";
                buttonDiv.id = `button${lift.id}-${dir}`;

                const container = document.createElement("div");
                container.className = "button-container";
                buttonDiv.appendChild(container);

                const button = document.createElement("button");
                button.className = "button";
                button.textContent = label;
                button.addEventListener("pointerdown", () => startLift(conId, lift.id, dir));
                button.addEventListener("pointerup", () => endLift(conId, lift.id, dir));
                button.addEventListener("pointerleave", () => endLift(conId, lift.id, dir));

                container.appendChild(button);

                const indicator = document.createElement("div");
                indicator.className = "indicator";
                indicator.id = `indicator${lift.id}-${dir}`;
                buttonDiv.appendChild(indicator);

                table.appendChild(buttonDiv);
            });

            liftsDiv.appendChild(liftDiv);
        }
    }
}

function emergencyStop() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ case: "stop" }));
    }
}

// Visibility handling
(function() {
    let hidden = "hidden";
    if (hidden in document) document.addEventListener("visibilitychange", handleVisibility);
    else if ((hidden = "mozHidden") in document) document.addEventListener("mozvisibilitychange", handleVisibility);
    else if ((hidden = "webkitHidden") in document) document.addEventListener("webkitvisibilitychange", handleVisibility);
    else if ((hidden = "msHidden") in document) document.addEventListener("msvisibilitychange", handleVisibility);
    else {
        window.onfocus = window.onpageshow = handleVisibility;
        window.onblur = window.onpagehide = handleVisibility;
    }

    function handleVisibility(evt) {
        const type = evt.type;
        if (["focus", "focusin", "pageshow"].includes(type)) startup();
        else disconnect();
    }

    if (document[hidden] !== undefined) {
        handleVisibility({ type: document[hidden] ? "blur" : "focus" });
    }
})();
