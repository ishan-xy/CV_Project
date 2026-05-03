const video    = document.getElementById("video");
const statusEl = document.getElementById("status");
const loader   = document.getElementById("loader");

let pc           = null;
let retryTimeout = null;
let isConnecting = false;

function setStatus(text) { if (statusEl) statusEl.textContent = text; }
function setLoader(visible) { if (loader) loader.style.display = visible ? "block" : "none"; }

function destroyPeerConnection() {
    if (!pc) return;
    pc.ontrack = pc.oniceconnectionstatechange =
    pc.onconnectionstatechange = pc.onsignalingstatechange = null;
    if (pc.signalingState !== "closed") pc.close();
    pc = null;
}

function scheduleRetry(delayMs = 3000) {
    if (retryTimeout) return;
    retryTimeout = setTimeout(() => { retryTimeout = null; startConnection(); }, delayMs);
}

function cancelRetry() {
    if (retryTimeout) { clearTimeout(retryTimeout); retryTimeout = null; }
}

async function startConnection() {
    if (isConnecting) return;
    isConnecting = true;
    cancelRetry();
    destroyPeerConnection();
    video.srcObject = null;
    setStatus("Initializing...");
    setLoader(true);

    pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.ontrack = (event) => {
        video.srcObject = event.streams[0];
        video.play().catch(() => {});
    };

    pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        console.log("ICE:", state);
        if (state === "checking") {
            setStatus("Connecting...");
        } else if (state === "connected" || state === "completed") {
            setStatus("Connected");
            setLoader(false);
        } else if (state === "failed") {
            setStatus("Connection failed, retrying...");
            setLoader(true);
            destroyPeerConnection();
            isConnecting = false;
            scheduleRetry();
        } else if (state === "disconnected") {
            setStatus("Disconnected, retrying...");
            setLoader(true);
            destroyPeerConnection();
            isConnecting = false;
            scheduleRetry(2000);
        } else if (state === "closed") {
            isConnecting = false;
        }
    };

    pc.onconnectionstatechange = () => {
        const state = pc.connectionState;
        console.log("Connection:", state);
        if (state === "failed") {
            setStatus("Connection failed, retrying...");
            setLoader(true);
            destroyPeerConnection();
            isConnecting = false;
            scheduleRetry();
        }
    };

    try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const response = await fetch("http://localhost:9000/offer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type })
        });

        if (!response.ok) throw new Error("Server error: " + response.status);

        const answer = await response.json();
        if (!pc || pc.signalingState === "closed") { isConnecting = false; return; }

        await pc.setRemoteDescription(answer);
        setStatus("Negotiating...");
    } catch (err) {
        console.error("WebRTC error:", err);
        setStatus("Error: " + err.message);
        setLoader(false);
        destroyPeerConnection();
        isConnecting = false;
        scheduleRetry(4000);
    } finally {
        isConnecting = false;
    }
}

window.addEventListener("load", () => startConnection());
window.addEventListener("beforeunload", () => { cancelRetry(); destroyPeerConnection(); });


const nameOverlay    = document.getElementById("name-overlay");
const overlayLabel   = document.getElementById("overlay-label");
const overlayName    = document.getElementById("overlay-name");
const overlayBooking = document.getElementById("overlay-booking");
const toast          = document.getElementById("toast");
const checkinBtn     = document.getElementById("checkin-btn");
const checkoutBtn    = document.getElementById("checkout-btn");

let currentBookingId = null;
let currentName      = null;
let toastTimer       = null;

function loadStore() {
    try { return JSON.parse(localStorage.getItem("checkin_store") || "{}"); }
    catch { return {}; }
}

function saveStore(store) {
    localStorage.setItem("checkin_store", JSON.stringify(store));
}

function todayISO() {
    return new Date().toISOString().slice(0, 10);
}

function showToast(msg, isError = false) {
    if (toastTimer) clearTimeout(toastTimer);
    toast.textContent = msg;
    toast.className = "show" + (isError ? " error" : "");
    toastTimer = setTimeout(() => { toast.className = ""; }, 3200);
}

function refreshButtonState() {
    const isUnknown = !currentBookingId;

    if (isUnknown) {
        checkinBtn.disabled       = true;
        checkinBtn.style.display  = "inline-block";
        checkoutBtn.style.display = "none";
        return;
    }

    const store  = loadStore();
    const record = store[currentBookingId];

    if (!record || !record.checkedIn) {
        checkinBtn.disabled       = false;
        checkinBtn.style.display  = "inline-block";
        checkoutBtn.style.display = "none";
    } else if (record.checkedIn && !record.checkedOut) {
        checkinBtn.style.display  = "none";
        checkoutBtn.style.display = "inline-block";
        checkoutBtn.disabled      = false;
    } else {
        checkinBtn.style.display  = "none";
        checkoutBtn.style.display = "none";
    }
}

function updateOverlay(name, bookingId) {
    const isUnknown = !bookingId || name === "Unknown";

    overlayName.textContent    = name;
    overlayLabel.textContent   = isUnknown ? "No guest detected" : "Guest";
    overlayBooking.textContent = isUnknown ? "" : bookingId;

    overlayName.classList.toggle("unknown", isUnknown);
    overlayLabel.classList.toggle("unknown", isUnknown);
}

function connectZMQ() {
    const ws = new WebSocket("ws://localhost:5556");

    ws.onopen = () => console.log("ZMQ bridge connected");

    ws.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); } catch { return; }

        const { booking_id, name } = data;
        const isUnknown = !booking_id || name === "Unknown";

        currentBookingId = isUnknown ? null : booking_id;
        currentName      = name;

        updateOverlay(name, booking_id);
        refreshButtonState();
    };

    ws.onclose = () => {
        console.log("ZMQ bridge disconnected, retrying in 3s...");
        setTimeout(connectZMQ, 3000);
    };

    ws.onerror = (e) => {
        console.error("ZMQ WS error:", e);
        ws.close();
    };
}

connectZMQ();


checkinBtn.addEventListener("click", async () => {
    if (!currentBookingId) return;
    checkinBtn.disabled = true;

    try {
        const res = await fetch("http://127.0.0.1:8000/checkin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ booking_id: currentBookingId, actual_check_in: todayISO() })
        });

        if (!res.ok) throw new Error(`Server returned ${res.status}`);

        const store = loadStore();
        store[currentBookingId] = {
            name: currentName,
            checkedIn: true,
            checkedInDate: todayISO(),
            checkedOut: false
        };
        saveStore(store);

        showToast(`✓ ${currentName} checked in`);
        refreshButtonState();
    } catch (err) {
        console.error("Check-in error:", err);
        showToast("Check-in failed: " + err.message, true);
        checkinBtn.disabled = false;
    }
});


checkoutBtn.addEventListener("click", async () => {
    if (!currentBookingId) return;
    checkoutBtn.disabled = true;

    try {
        const res = await fetch("http://127.0.0.1:8000/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ booking_id: currentBookingId, actual_check_out: todayISO() })
        });

        if (!res.ok) throw new Error(`Server returned ${res.status}`);

        const store = loadStore();
        if (store[currentBookingId]) {
            store[currentBookingId].checkedOut     = true;
            store[currentBookingId].checkedOutDate = todayISO();
        }
        saveStore(store);

        showToast(`↩ ${currentName} checked out`);
        refreshButtonState();
    } catch (err) {
        console.error("Check-out error:", err);
        showToast("Check-out failed: " + err.message, true);
        checkoutBtn.disabled = false;
    }
});