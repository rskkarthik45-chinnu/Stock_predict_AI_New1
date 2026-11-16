// ======================================
// ADMIN DASHBOARD JAVASCRIPT
// ======================================

document.addEventListener("DOMContentLoaded", function () {

    console.log("Admin Dashboard Loaded Successfully!");

    // ==================================
    // 1. USER SEARCH
    // ==================================

    const searchInput = document.getElementById("userSearch");

    if (searchInput) {

        searchInput.addEventListener("keyup", function () {

            let searchValue = searchInput.value.toLowerCase();

            const tableRows = document.querySelectorAll(
                "#usersTable tbody tr"
            );

            tableRows.forEach(function (row) {

                let rowText = row.innerText.toLowerCase();

                row.style.display = rowText.includes(searchValue)
                    ? ""
                    : "none";

            });

        });

    }


    // ==================================
    // 2. DELETE USER CONFIRMATION
    // ==================================

    const deleteButtons = document.querySelectorAll(".delete-btn");

    deleteButtons.forEach(function (button) {

        button.addEventListener("click", function (event) {

            const confirmed = confirm(
                "Are you sure you want to delete this user?"
            );

            if (!confirmed) {
                event.preventDefault();
            }

        });

    });


    // ==================================
    // 3. BLOCK / UNBLOCK CONFIRMATION
    // ==================================

    const blockButtons = document.querySelectorAll(".block-btn");

    blockButtons.forEach(function (button) {

        button.addEventListener("click", function (event) {

            const confirmed = confirm(
                "Are you sure you want to change this user's status?"
            );

            if (!confirmed) {
                event.preventDefault();
            }

        });

    });


    // ==================================
    // 4. SIDEBAR ACTIVE LINK
    // ==================================

    const sidebarLinks = document.querySelectorAll(".sidebar a");

    sidebarLinks.forEach(function (link) {

        if (link.href === window.location.href) {

            link.classList.add("active");

        }

    });


    // ==================================
    // 5. FLASH MESSAGE AUTO HIDE
    // ==================================

    const flashMessages = document.querySelectorAll(".flash-message");

    flashMessages.forEach(function (message) {

        setTimeout(function () {

            message.style.opacity = "0";

            setTimeout(function () {

                message.remove();

            }, 500);

        }, 4000);

    });


    // ==================================
    // 6. CURRENT DATE
    // ==================================

    const dateElement = document.getElementById("currentDate");

    if (dateElement) {

        const today = new Date();

        dateElement.textContent = today.toLocaleDateString(
            "en-IN",
            {
                day: "numeric",
                month: "long",
                year: "numeric"
            }
        );

    }


    // ==================================
    // 7. MOBILE SIDEBAR
    // ==================================

    const menuButton = document.getElementById("menuToggle");

    const sidebar = document.querySelector(".sidebar");

    if (menuButton && sidebar) {

        menuButton.addEventListener("click", function () {

            sidebar.classList.toggle("show");

        });

    }

});