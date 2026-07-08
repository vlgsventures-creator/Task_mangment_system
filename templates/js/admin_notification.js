// =========================================
// Admin Notification JS (Part 3A)
// =========================================

let notifications = [];
let filteredNotifications = [];

// -----------------------------
// Load Notifications
// -----------------------------

async function loadNotifications(){

    const container = document.getElementById("notificationContainer");

    container.innerHTML = `
        <div class="loading">
            <i class="fa-solid fa-spinner fa-spin"></i>
            <p>Loading Notifications...</p>
        </div>
    `;

    try{

        const response = await fetch("/api/admin_notifications");

        notifications = await response.json();

        filteredNotifications = [...notifications];

        updateCounts();

        renderNotifications(filteredNotifications);

    }

    catch(error){

        console.log(error);

        container.innerHTML = `
            <div class="empty">
                <i class="fa-solid fa-circle-exclamation"></i>

                <h2>Unable to load notifications</h2>

                <p>Please try again.</p>

            </div>
        `;

    }

}

// -----------------------------
// Render Notifications
// -----------------------------

function renderNotifications(data){

    const container=document.getElementById("notificationContainer");

    container.innerHTML="";

    if(data.length===0){

        container.innerHTML=`

            <div class="empty">

                <i class="fa-regular fa-bell-slash"></i>

                <h2>No Notifications</h2>

                <p>Everything is up to date.</p>

            </div>

        `;

        return;

    }

    data.forEach(item=>{

        let icon="fa-bell";
        let color="blue";
        let badge="assigned";

        switch(item.type){

            case "Assigned":

                icon="fa-list-check";
                color="blue";
                badge="assigned";

                break;

            case "Completed":

                icon="fa-circle-check";
                color="green";
                badge="completed";

                break;

            case "Overdue":

                icon="fa-clock";
                color="red";
                badge="overdue";

                break;

            case "Deadline":

                icon="fa-calendar-days";
                color="orange";
                badge="warning";

                break;

        }

        container.innerHTML+=`

        <div class="notification-card ${item.is_read ? "" : "unread"}">

            <div class="icon ${color}">

                <i class="fa-solid ${icon}"></i>

            </div>

            <div class="content">

                <div class="top">

                    <h3>${item.title}</h3>

                    <span>${formatTime(item.created_at)}</span>

                </div>

                <p>${item.message}</p>

                <div class="bottom">

                    <span class="badge ${badge}">

                        ${item.type}

                    </span>

                    <button onclick="markRead(${item.id})">

                        Mark Read

                    </button>

                </div>

            </div>

        </div>

        `;

    });

}

// -----------------------------
// Dashboard Counts
// -----------------------------

function updateCounts(){

    document.getElementById("totalNotification").innerText =
        notifications.length;

    document.getElementById("unreadNotification").innerText =
        notifications.filter(n=>!n.is_read).length;

}

// -----------------------------
// Search
// -----------------------------

document.getElementById("searchInput")
.addEventListener("keyup",function(){

    const value=this.value.toLowerCase();

    filteredNotifications=notifications.filter(n=>

        n.title.toLowerCase().includes(value) ||

        n.message.toLowerCase().includes(value)

    );

    renderNotifications(filteredNotifications);

});

// -----------------------------
// Refresh
// -----------------------------

document.getElementById("refreshBtn")
.addEventListener("click",loadNotifications);

// -----------------------------

loadNotifications();
// =========================================
// Part 3B
// =========================================

// -----------------------------
// Relative Time
// -----------------------------

function formatTime(dateString){

    const created = new Date(dateString);

    const now = new Date();

    const seconds = Math.floor((now-created)/1000);

    const minutes = Math.floor(seconds/60);

    const hours = Math.floor(minutes/60);

    const days = Math.floor(hours/24);

    if(seconds<60) return "Just now";

    if(minutes<60) return minutes+" min ago";

    if(hours<24) return hours+" hr ago";

    if(days===1) return "Yesterday";

    if(days<7) return days+" days ago";

    return created.toLocaleDateString();

}

// -----------------------------
// Filter Buttons
// -----------------------------

document.querySelectorAll(".filter").forEach(btn=>{

    btn.addEventListener("click",function(){

        document
        .querySelectorAll(".filter")
        .forEach(x=>x.classList.remove("active"));

        this.classList.add("active");

        const type=this.dataset.filter;

        if(type==="All"){

            filteredNotifications=[...notifications];

        }

        else{

            filteredNotifications=
            notifications.filter(n=>n.type===type);

        }

        renderNotifications(filteredNotifications);

    });

});

// -----------------------------
// Mark Single Read
// -----------------------------

async function markRead(id){

    try{

        await fetch("/api/read_notification/"+id,{

            method:"PUT"

        });

        const item=notifications.find(x=>x.id===id);

        if(item){

            item.is_read=true;

        }

        updateCounts();

        renderNotifications(filteredNotifications);

    }

    catch(error){

        console.log(error);

        alert("Unable to update notification.");

    }

}

// -----------------------------
// Mark All Read
// -----------------------------

document
.getElementById("markAllRead")
.addEventListener("click",async()=>{

    try{

        await fetch("/api/read_all_notifications",{

            method:"PUT"

        });

        notifications.forEach(n=>{

            n.is_read=true;

        });

        filteredNotifications=[...notifications];

        updateCounts();

        renderNotifications(filteredNotifications);

    }

    catch(error){

        console.log(error);

    }

});

// -----------------------------
// Auto Refresh
// -----------------------------

setInterval(()=>{

    loadNotifications();

},30000);

// -----------------------------
// Refresh Badge
// -----------------------------

async function refreshBadge(){

    try{

        const response=await fetch("/api/admin_notification_count");

        const data=await response.json();

        const badge=document.getElementById("notificationCount");

        if(badge){

            badge.innerText=data.count;

            badge.style.display=data.count>0?"flex":"none";

        }

    }

    catch(error){

        console.log(error);

    }

}

// Every 10 Seconds

setInterval(refreshBadge,10000);

refreshBadge();