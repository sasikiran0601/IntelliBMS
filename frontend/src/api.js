(function attachApi(global) {
    async function fetchJson(url, options) {
        const response = await fetch(url, options);
        const payload = await response.json().catch(function parseFallback() {
            return {};
        });

        if (!response.ok) {
            const message = payload.detail || payload.message || "Request failed";
            throw new Error(message);
        }

        return payload;
    }

    global.IntelliBMSApi = {
        getBatteryCatalog: function getBatteryCatalog() {
            return fetchJson("/api/batteries");
        },
        createBattery: function createBattery(payload) {
            return fetchJson("/api/batteries", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
        },
        deleteBattery: function deleteBattery(id) {
            return fetchJson("/api/batteries/" + id, {
                method: "DELETE",
            });
        },
        uploadBatteryFiles: function uploadBatteryFiles(files) {
            const formData = new FormData();
            Array.from(files).forEach(function appendFile(file) {
                formData.append("files", file);
            });

            return fetchJson("/api/batteries/upload", {
                method: "POST",
                body: formData,
            });
        },
        getLiveData: function getLiveData(selection) {
            const scope = selection.source === "preset" ? "preset" : "custom";
            return fetchJson("/api/batteries/" + scope + "/" + selection.id + "/live-data");
        },
    };
})(window);
