function mountApp() {
    const App = window.IntelliBMSApp;
    if (!App) {
        setTimeout(mountApp, 50);
        return;
    }
    const container = document.getElementById("root");
    if (container) {
        const root = ReactDOM.createRoot(container);
        root.render(<App />);
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountApp);
} else {
    mountApp();
}
