// Function to toggle visibility of a section (for collapsible sections)
function toggleSection(id) {
    const section = document.getElementById(id);
    section.classList.toggle("hidden");
}

// Language Switcher Functionality
const languageSwitcher = document.getElementById('language-switcher');
languageSwitcher.addEventListener('click', () => {
    // Toggle between 'ENG' and 'PL'
    if (languageSwitcher.textContent === 'ENG') {
        languageSwitcher.textContent = 'PL';
        // Save the language preference in a cookie
        document.cookie = 'language=PL; path=/; max-age=' + 60 * 60 * 24 * 365;
    } else {
        languageSwitcher.textContent = 'ENG';
        // Save the language preference in a cookie
        document.cookie = 'language=ENG; path=/; max-age=' + 60 * 60 * 24 * 365;
    }
});

// Set language on page load from cookie (defaults to ENG)
const savedLanguage = document.cookie.replace(/(?:(?:^|.*;\s*)language\s*=\s*([^;]*).*$)|^.*$/, "$1") || 'ENG';
languageSwitcher.textContent = savedLanguage;

// Display Current Date (Day, Date, Month)
function updateDate() {
    const dateElement = document.getElementById('date');
    const currentDate = new Date();
    const options = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
    dateElement.textContent = currentDate.toLocaleDateString('en-US', options);
}

updateDate(); // Initialize date

const themeIcon = document.getElementById("theme-icon");

// Theme Toggle Script
document.getElementById('theme-toggle').addEventListener('click', function() {
    var icon = document.getElementById('theme-icon');
    var currentTheme = document.documentElement.getAttribute('data-theme');
    
    // Toggle between moon and sun icons and set theme accordingly
    if (currentTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'light');
        icon.classList.remove('fa-sun');
        icon.classList.add('fa-moon');
        // Save the theme preference in a cookie
        document.cookie = 'theme=light; path=/; max-age=' + 60 * 60 * 24 * 365;
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        icon.classList.remove('fa-moon');
        icon.classList.add('fa-sun');
        // Save the theme preference in a cookie
        document.cookie = 'theme=dark; path=/; max-age=' + 60 * 60 * 24 * 365;
    }
});

// Set theme on page load from cookie (defaults to dark theme)
const savedTheme = document.cookie.replace(/(?:(?:^|.*;\s*)theme\s*=\s*([^;]*).*$)|^.*$/, "$1") || 'dark';
if (savedTheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    themeIcon.classList.replace('fa-sun', 'fa-moon');
} else {
    document.documentElement.setAttribute('data-theme', 'light');
    themeIcon.classList.replace('fa-moon', 'fa-sun');
}

// Sidebar Section Toggle (for maintaining collapsible section state)
document.addEventListener("DOMContentLoaded", function() {
    const loansSection = document.getElementById('loans-section');
    const reportsSection = document.getElementById('reports-section');
    
    // Restore the previous state of the "Loans" section
    if (localStorage.getItem('loans-expanded') === 'true') {
        loansSection.open = true;
    } else {
        loansSection.open = false;
    }

    // Restore the previous state of the "Reports" section
    if (localStorage.getItem('reports-expanded') === 'true') {
        reportsSection.open = true;
    } else {
        reportsSection.open = false;
    }

    // Save the state of "Loans" section to localStorage when toggled
    loansSection.addEventListener('toggle', function() {
        localStorage.setItem('loans-expanded', loansSection.open);
    });

    // Save the state of "Reports" section to localStorage when toggled
    reportsSection.addEventListener('toggle', function() {
        localStorage.setItem('reports-expanded', reportsSection.open);
    });
});


document.addEventListener("DOMContentLoaded", function () {
    flatpickr("#start_date", {
      dateFormat: "Y-m-d",  // Customize the date format
      defaultDate: "today", // Set default date as today
    });
  });