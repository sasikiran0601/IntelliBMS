const { useDeferredValue, useEffect, useMemo, useRef, useState, startTransition } = React;
const RechartsLib = window.Recharts || {};
const {
    ResponsiveContainer,
    LineChart: RechartsLineChart,
    Line: RechartsLine,
    XAxis: RechartsXAxis,
    YAxis: RechartsYAxis,
    CartesianGrid: RechartsCartesianGrid,
    Tooltip: RechartsTooltip,
    ReferenceLine: RechartsReferenceLine,
    ReferenceArea: RechartsReferenceArea,
    Dot: RechartsDot,
} = RechartsLib;

const NAV_ITEMS = [
    { key: "dashboard", label: "Dashboard" },
    { key: "preset", label: "Preset Batteries" },
    { key: "custom", label: "Custom Batteries" },
    { key: "add", label: "Add Battery" },
    { key: "import", label: "Import Files" },
];

const DEFAULT_FORM = {
    name: "",
    battery_type: "Li-ion",
    num_cells: 48,
    base_voltage: 4.1,
    base_soh: 95,
    base_temp: 25,
    degradation_rate: 0.03,
    fault_probability: 0.1,
    capacity_ah: 100,
    max_charge_rate: 50,
    max_discharge_rate: 100,
    operating_temp_min: -10,
    operating_temp_max: 60,
    description: "Custom battery configuration",
};

function createOrUpdateChart(chartRef, canvasRef, config) {
    if (!canvasRef.current) {
        return;
    }

    if (chartRef.current) {
        chartRef.current.destroy();
    }

    chartRef.current = new Chart(canvasRef.current.getContext("2d"), config);
}

function destroyChart(chartRef) {
    if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
    }
}

function formatMetric(value, suffix, digits) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "--";
    }

    return Number(value).toFixed(digits) + suffix;
}

function selectionKey(selection) {
    return selection ? selection.source + ":" + selection.id : "";
}

function selectPreferredBattery(catalog, preferred) {
    const combined = catalog.predefined.concat(catalog.custom);
    if (!combined.length) {
        return null;
    }

    if (!preferred) {
        return combined[0];
    }

    return combined.find(function findMatch(item) {
        return item.id === preferred.id && item.source === preferred.source;
    }) || combined[0];
}

function Sidebar({ activeSection, onSectionChange }) {
    return (
        <aside className="sidebar">
            <div className="brand-block">
                <p className="brand-kicker">IntelliBMS</p>
                <h1>Battery Monitor</h1>
                <p>Minimal monitoring workspace with light surfaces and live battery metrics.</p>
            </div>

            <nav className="nav-list">
                {NAV_ITEMS.map(function renderItem(item) {
                    return (
                        <button
                            key={item.key}
                            className={"nav-item" + (activeSection === item.key ? " active" : "")}
                            onClick={function handleClick() {
                                onSectionChange(item.key);
                            }}
                            type="button"
                        >
                            {item.label}
                        </button>
                    );
                })}
            </nav>
        </aside>
    );
}

function BatteryGrid({ items, onDelete, selected, title, onSelect }) {
    return (
        <section className="panel">
            <div className="panel-header">
                <h2>{title}</h2>
                <span>{items.length}</span>
            </div>
            <div className="selection-grid">
                {items.map(function renderBattery(item) {
                    const active = selected && item.id === selected.id && item.source === selected.source;
                    return (
                        <button
                            key={item.source + "-" + item.id}
                            className={"selection-card" + (active ? " active" : "")}
                            onClick={function handleSelect() {
                                onSelect(item);
                            }}
                            type="button"
                        >
                            <strong>{item.name}</strong>
                            <span>{item.battery_type}</span>
                            <p>{item.num_cells} cells / {formatMetric(item.base_voltage, "V", 2)}</p>
                            <p>SOH {formatMetric(item.base_soh, "%", 1)}</p>
                            {onDelete ? (
                                <span
                                    className="delete-link"
                                    onClick={function handleDelete(event) {
                                        event.stopPropagation();
                                        onDelete(item.id);
                                    }}
                                >
                                    Delete
                                </span>
                            ) : null}
                        </button>
                    );
                })}
            </div>
        </section>
    );
}

function BatteryForm({ form, notice, onChange, onSubmit, submitting }) {
    return (
        <section className="panel form-panel">
            <div className="panel-header">
                <h2>Add Battery</h2>
                <span>Minimal form</span>
            </div>
            {notice ? <div className="notice inline">{notice}</div> : null}
            <form className="stack" onSubmit={onSubmit}>
                <div className="field-grid">
                    <label>
                        <span>Name</span>
                        <input required value={form.name} onChange={function (event) { onChange("name", event.target.value); }} />
                    </label>
                    <label>
                        <span>Type</span>
                        <input value={form.battery_type} onChange={function (event) { onChange("battery_type", event.target.value); }} />
                    </label>
                    <label>
                        <span>Cells</span>
                        <input min="1" type="number" value={form.num_cells} onChange={function (event) { onChange("num_cells", Number(event.target.value)); }} />
                    </label>
                    <label>
                        <span>Base Voltage</span>
                        <input step="0.01" type="number" value={form.base_voltage} onChange={function (event) { onChange("base_voltage", Number(event.target.value)); }} />
                    </label>
                    <label>
                        <span>Base SOH</span>
                        <input step="0.1" type="number" value={form.base_soh} onChange={function (event) { onChange("base_soh", Number(event.target.value)); }} />
                    </label>
                    <label>
                        <span>Base Temperature</span>
                        <input step="0.1" type="number" value={form.base_temp} onChange={function (event) { onChange("base_temp", Number(event.target.value)); }} />
                    </label>
                    <label>
                        <span>Degradation</span>
                        <input step="0.01" type="number" value={form.degradation_rate} onChange={function (event) { onChange("degradation_rate", Number(event.target.value)); }} />
                    </label>
                    <label>
                        <span>Fault Probability</span>
                        <input step="0.1" type="number" value={form.fault_probability} onChange={function (event) { onChange("fault_probability", Number(event.target.value)); }} />
                    </label>
                </div>

                <label>
                    <span>Description</span>
                    <textarea rows="3" value={form.description} onChange={function (event) { onChange("description", event.target.value); }} />
                </label>

                <button className="toolbar-button primary" disabled={submitting} type="submit">
                    {submitting ? "Saving..." : "Save Battery"}
                </button>
            </form>
        </section>
    );
}

function UploadPanel({ notice, onUpload, uploading }) {
    const inputRef = useRef(null);

    return (
        <section className="panel form-panel">
            <div className="panel-header">
                <h2>Import Files</h2>
                <span>CSV / XLSX / JSON / TXT</span>
            </div>
            {notice ? <div className="notice inline">{notice}</div> : null}
            <div className="stack">
                <input multiple ref={inputRef} type="file" />
                <button
                    className="toolbar-button primary"
                    disabled={uploading}
                    onClick={async function handleUpload() {
                        if (!inputRef.current || !inputRef.current.files.length) {
                            return;
                        }

                        await onUpload(inputRef.current.files);
                        inputRef.current.value = "";
                    }}
                    type="button"
                >
                    {uploading ? "Uploading..." : "Upload and Create"}
                </button>
            </div>
        </section>
    );
}

function ConfirmDialog({ onCancel, onConfirm, open, title }) {
    if (!open) {
        return null;
    }

    return (
        <div className="confirm-backdrop" onClick={onCancel}>
            <div
                className="confirm-dialog"
                onClick={function stopPropagation(event) {
                    event.stopPropagation();
                }}
            >
                <h3>{title}</h3>
                <p>This action will permanently remove the custom battery.</p>
                <div className="confirm-actions">
                    <button className="toolbar-button subtle" onClick={onCancel} type="button">
                        Cancel
                    </button>
                    <button className="toolbar-button danger" onClick={onConfirm} type="button">
                        Delete
                    </button>
                </div>
            </div>
        </div>
    );
}

function MetricCard({ tone, label, value }) {
    return (
        <div className={"metric-card " + tone}>
            <div className="metric-label">{label}</div>
            <div className="metric-value">{value}</div>
        </div>
    );
}

function MonitoringCharts({ liveData }) {
    const deferredLiveData = useDeferredValue(liveData);
    const [zoom, setZoom] = useState("all");

    function clampSoh(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return null;
        }
        return Math.max(0, Math.min(100, numeric));
    }

    function formatDateLabel(timestamp) {
        return new Date(timestamp * 1000).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }

    function filterHistoryData(data, activeZoom) {
        if (activeZoom === "30") {
            return data.slice(-30);
        }
        if (activeZoom === "60") {
            return data.slice(-60);
        }
        return data;
    }

    function buildTickValues(data) {
        if (!data.length) {
            return [];
        }

        const step = Math.max(1, Math.ceil(data.length / 5));
        const ticks = [];
        for (let index = 0; index < data.length; index += step) {
            ticks.push(data[index].timestamp);
        }
        if (ticks[ticks.length - 1] !== data[data.length - 1].timestamp) {
            ticks.push(data[data.length - 1].timestamp);
        }
        return ticks;
    }

    function buildAxisTicks(domainMin, domainMax, threshold) {
        const values = [domainMin, threshold, domainMax];
        const lowerMid = Math.round((domainMin + threshold) / 2);
        const upperMid = Math.round((threshold + domainMax) / 2);
        values.push(lowerMid, upperMid);
        return values.filter(function filterTicks(value, index, array) {
            return Number.isFinite(value) && array.indexOf(value) === index;
        }).sort(function sortTicks(a, b) { return a - b; });
    }

    function buildForecastTickValues(data) {
        if (!data.length) {
            return [];
        }

        const preferredIndexes = [0, 6, 12, 18, 24];
        const ticks = preferredIndexes
            .map(function mapIndex(index) { return data[index] ? data[index].timestamp : null; })
            .filter(function filterNull(value, index, array) {
                return value !== null && array.indexOf(value) === index;
            });

        if (!ticks.length) {
            return buildTickValues(data);
        }

        if (ticks[ticks.length - 1] !== data[data.length - 1].timestamp) {
            ticks.push(data[data.length - 1].timestamp);
        }

        return ticks;
    }

    function buildYAxis(values, threshold, minimumFloor) {
        const numericValues = values
            .map(function (value) { return Number(value); })
            .filter(function (value) { return Number.isFinite(value); });
        const allValues = numericValues.concat([threshold]);

        if (!allValues.length) {
            return [minimumFloor, 100];
        }

        const minValue = Math.min.apply(null, allValues);
        const maxValue = Math.max.apply(null, allValues);
        const paddedMin = Math.max(minimumFloor, Math.floor((minValue - 2) / 2) * 2);
        const paddedMax = Math.min(100, Math.ceil((maxValue + 2) / 2) * 2);
        return [paddedMin, paddedMax];
    }

    function buildForecastScale(values, threshold) {
        const numericValues = values
            .map(function (value) { return Number(value); })
            .filter(function (value) { return Number.isFinite(value); });

        if (!numericValues.length) {
            return {
                domain: [70, 100],
                ticks: [70, 80, 90, 100],
                showThresholdInChart: true,
                criticalRange: false,
            };
        }

        const minValue = Math.min.apply(null, numericValues);
        const maxValue = Math.max.apply(null, numericValues);
        const allCritical = maxValue <= threshold - 12;

        if (allCritical) {
            const domainMin = Math.max(0, Math.floor((minValue - 4) / 5) * 5);
            let domainMax = Math.min(100, Math.ceil((maxValue + 4) / 5) * 5);
            if (domainMax - domainMin < 20) {
                domainMax = Math.min(100, domainMin + 20);
            }
            const ticks = [domainMin, domainMin + 5, domainMin + 10, domainMax]
                .filter(function (value, index, array) {
                    return Number.isFinite(value) && value <= domainMax && array.indexOf(value) === index;
                })
                .sort(function (a, b) { return a - b; });

            return {
                domain: [domainMin, domainMax],
                ticks: ticks,
                showThresholdInChart: false,
                criticalRange: true,
            };
        }

        const domain = buildYAxis(numericValues, threshold, 0);
        return {
            domain: domain,
            ticks: buildAxisTicks(domain[0], domain[1], threshold),
            showThresholdInChart: true,
            criticalRange: false,
        };
    }

    function buildHistoryScale(values, threshold) {
        const numericValues = values
            .map(function (value) { return Number(value); })
            .filter(function (value) { return Number.isFinite(value); });

        if (!numericValues.length) {
            return {
                domain: [90, 100],
                ticks: [90, 95, 100],
                showThresholdInChart: true,
                criticalRange: false,
            };
        }

        const minValue = Math.min.apply(null, numericValues);
        const maxValue = Math.max.apply(null, numericValues);
        const allCritical = maxValue <= threshold - 10;

        if (allCritical) {
            const domainMin = Math.max(0, Math.floor((minValue - 4) / 5) * 5);
            let domainMax = Math.min(100, Math.ceil((maxValue + 4) / 5) * 5);
            if (domainMax - domainMin < 20) {
                domainMax = Math.min(100, domainMin + 20);
            }

            const ticks = [domainMin, domainMin + 5, domainMin + 10, domainMax]
                .filter(function (value, index, array) {
                    return Number.isFinite(value) && value <= domainMax && array.indexOf(value) === index;
                })
                .sort(function (a, b) { return a - b; });

            return {
                domain: [domainMin, domainMax],
                ticks: ticks,
                showThresholdInChart: false,
                criticalRange: true,
            };
        }

        const domain = buildYAxis(numericValues, threshold, 0);
        return {
            domain: domain,
            ticks: buildAxisTicks(domain[0], domain[1], threshold),
            showThresholdInChart: true,
            criticalRange: false,
        };
    }

    function sanitizeSeries(points, valueKey) {
        const byTimestamp = {};

        points.forEach(function eachPoint(point) {
            const timestamp = Number(point.timestamp);
            const value = clampSoh(point[valueKey]);

            if (!Number.isFinite(timestamp) || value === null) {
                return;
            }

            byTimestamp[timestamp] = Object.assign({}, point, {
                timestamp: timestamp,
                [valueKey]: value,
            });
        });

        return Object.keys(byTimestamp)
            .map(function toPoint(key) { return byTimestamp[key]; })
            .sort(function sortPoints(a, b) { return a.timestamp - b.timestamp; });
    }

    const historySource = useMemo(function () {
        const forecastData = deferredLiveData && deferredLiveData.long_term_forecast ? deferredLiveData.long_term_forecast : { history: [] };
        return sanitizeSeries((forecastData.history || []).map(function (point) {
            return {
                timestamp: Number(point.timestamp),
                dateStr: new Date(point.timestamp * 1000).toISOString().split("T")[0],
                soh: clampSoh(point.soh),
            };
        }), "soh");
    }, [deferredLiveData]);

    const projectionSource = useMemo(function () {
        const forecastData = deferredLiveData && deferredLiveData.long_term_forecast ? deferredLiveData.long_term_forecast : { projection: [] };
        return sanitizeSeries((forecastData.projection || []).map(function (point) {
            return {
                timestamp: Number(point.x),
                projected: clampSoh(point.y),
            };
        }), "projected");
    }, [deferredLiveData]);

    const historyData = useMemo(function () {
        return filterHistoryData(historySource, zoom);
    }, [historySource, zoom]);

    const historyTicks = useMemo(function () {
        return buildTickValues(historyData);
    }, [historyData]);

    const historyValues = historyData.map(function (item) { return item.soh; });
    const currentSOH = historyValues.length ? historyValues[historyValues.length - 1] : null;
    const peakSOH = historyValues.length ? Math.max.apply(null, historyValues) : null;
    const peakPoint = peakSOH === null ? null : historyData.find(function (item) { return item.soh === peakSOH; }) || null;
    const averageSOH = historyValues.length
        ? (historyValues.reduce(function (sum, value) { return sum + value; }, 0) / historyValues.length)
        : null;
    const isHealthy = currentSOH !== null ? currentSOH >= 95 : true;
    const historyScale = buildHistoryScale(historyValues, 95);
    const historyDomain = historyScale.domain;

    const forecastData = useMemo(function () {
        const projection = projectionSource.map(function (point, index) {
            return {
                timestamp: Number(point.timestamp),
                dateStr: new Date(point.timestamp * 1000).toISOString().split("T")[0],
                label: formatDateLabel(point.timestamp),
                sublabel:
                    index === 5 ? "(6 months)"
                        : index === 11 ? "(12 months)"
                            : index === 17 ? "(18 months)"
                                : index === 23 ? "(24 months)"
                                    : null,
                projected: clampSoh(point.projected),
                current: null,
                isStart: false,
                isEnd: index === projectionSource.length - 1,
            };
        });

        if (historyData.length) {
            projection.unshift({
                timestamp: historyData[historyData.length - 1].timestamp,
                dateStr: new Date(historyData[historyData.length - 1].timestamp * 1000).toISOString().split("T")[0],
                label: formatDateLabel(historyData[historyData.length - 1].timestamp),
                sublabel: "(Now)",
                projected: Number(historyData[historyData.length - 1].soh),
                current: Number(historyData[historyData.length - 1].soh),
                isStart: true,
                isEnd: false,
            });
        }

        return projection;
    }, [historyData, projectionSource]);

    const forecastTicks = useMemo(function () {
        return buildForecastTickValues(forecastData);
    }, [forecastData]);

    const forecastValues = forecastData.map(function (item) { return item.projected; });
    const forecastScale = buildForecastScale(forecastValues, 80);
    const forecastDomain = forecastScale.domain;
    const historyTicksY = historyScale.ticks;
    const forecastTicksY = forecastScale.ticks;
    const forecastEnd = forecastValues.length ? forecastValues[forecastValues.length - 1] : null;
    const forecastMin = forecastValues.length ? Math.min.apply(null, forecastValues) : null;
    const forecastStatus = forecastEnd !== null && forecastEnd >= 80 ? "Stable" : "Risk";
    const forecastLowestPoint = forecastMin === null
        ? null
        : forecastData.find(function (item) { return item.projected === forecastMin; }) || null;
    const forecastEndPoint = forecastData.length ? forecastData[forecastData.length - 1] : null;

    if (!ResponsiveContainer || !RechartsLineChart || !RechartsLine || !RechartsXAxis || !RechartsYAxis) {
        return (
            <section className="panel">
                <h2>Charts unavailable</h2>
                <p>Recharts did not load correctly. Refresh the page once to load the chart library.</p>
            </section>
        );
    }

    function HistoryTooltip({ active, payload, label }) {
        if (!active || !payload || !payload.length) {
            return null;
        }

        const value = payload[0].value;
        const safe = value >= 95;
        return (
            <div style={{
                background: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "10px 16px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.10)",
                fontSize: 13,
            }}>
                <div style={{ color: "#64748b", marginBottom: 2 }}>{formatDateLabel(label)}</div>
                <div style={{ fontWeight: 700, color: safe ? "#2563eb" : "#ef4444", fontSize: 16 }}>
                    SOH: {Number(value).toFixed(2)}%
                </div>
                <div style={{
                    marginTop: 4,
                    fontSize: 11,
                    color: safe ? "#16a34a" : "#dc2626",
                    background: safe ? "#f0fdf4" : "#fef2f2",
                    borderRadius: 5,
                    padding: "2px 8px",
                    display: "inline-block",
                }}>
                    {safe ? "Safe zone" : "Warning zone"}
                </div>
            </div>
        );
    }

    function ForecastTooltip({ active, payload, label }) {
        if (!active || !payload || !payload.length) {
            return null;
        }

        const point = forecastData.find(function (item) { return item.timestamp === label; });
        const value = payload.find(function (entry) { return entry.value !== null && entry.value !== undefined; });
        if (!point || !value) {
            return null;
        }

        return (
            <div style={{
                background: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: 10,
                padding: "10px 16px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.10)",
                fontSize: 13,
            }}>
                <div style={{ color: "#64748b", marginBottom: 2 }}>{point.label}</div>
                <div style={{ fontWeight: 700, color: point.isStart ? "#16a34a" : value.value >= 80 ? "#d97706" : "#dc2626", fontSize: 16 }}>
                    {point.isStart ? "Current SOH" : "Projected SOH"}: {Number(value.value).toFixed(2)}%
                </div>
            </div>
        );
    }

    function renderHistoryDot(props) {
        const payload = props.payload || {};
        if (payload.soh === peakSOH || payload.timestamp === (historyData[historyData.length - 1] || {}).timestamp) {
            return <RechartsDot cx={props.cx} cy={props.cy} r={5} fill="#2563eb" stroke="#fff" strokeWidth={2} />;
        }
        return <g />;
    }

    return (
        <div className="chart-grid">
            <section className="panel soh-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4, gap: 18, flexWrap: "wrap" }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: 26, fontWeight: 800, color: "#0f172a", letterSpacing: -0.5 }}>SOH History</h2>
                        <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13.5 }}>
                            {historyScale.criticalRange
                                ? "Critical-range history view is enabled so low SOH values remain readable over time."
                                : "Track the State of Health (SOH) over time. SOH above 95% is considered safe."}
                        </p>
                    </div>
                    <div style={{ display: "flex", gap: 20, alignItems: "center", fontSize: 12.5, color: "#475569", flexWrap: "wrap" }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ width: 24, height: 2.5, background: "#2563eb", display: "inline-block", borderRadius: 2 }} />
                            SOH (%)
                        </span>
                        {historyScale.showThresholdInChart ? (
                            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span style={{ width: 14, height: 14, background: "rgba(134,239,172,0.32)", border: "1.5px solid #86efac", display: "inline-block", borderRadius: 3 }} />
                                Safe zone (&gt;95%)
                            </span>
                        ) : null}
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ width: 14, height: 14, background: "rgba(252,165,165,0.3)", border: "1.5px solid #fca5a5", display: "inline-block", borderRadius: 3 }} />
                            {historyScale.showThresholdInChart ? "Warning zone (<95%)" : "Critical range"}
                        </span>
                    </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 14, margin: "22px 0 24px" }}>
                    {[
                        {
                            label: "CURRENT SOH",
                            value: currentSOH !== null ? currentSOH.toFixed(1) + "%" : "--",
                            sub: historyData.length ? "As of " + formatDateLabel(historyData[historyData.length - 1].timestamp) : "No data",
                            valueColor: "#2563eb",
                        },
                        {
                            label: "PEAK SOH",
                            value: peakSOH !== null ? peakSOH.toFixed(1) + "%" : "--",
                            sub: peakPoint ? formatDateLabel(peakPoint.timestamp) : "No peak",
                            valueColor: "#0f172a",
                        },
                        {
                            label: "AVERAGE SOH",
                            value: averageSOH !== null ? averageSOH.toFixed(1) + "%" : "--",
                            sub: "Over selected period",
                            valueColor: "#0f172a",
                        },
                        {
                            label: "STATUS",
                            badge: isHealthy ? "Healthy" : "Warning",
                            badgeColor: isHealthy ? { bg: "#dcfce7", text: "#16a34a" } : { bg: "#fee2e2", text: "#dc2626" },
                            sub: isHealthy ? "SOH is within the safe range" : "SOH is below threshold",
                        },
                    ].map(function renderCard(card, index) {
                        return (
                            <div key={index} style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: "16px 18px", background: "#fff" }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", letterSpacing: 0.8, marginBottom: 6 }}>
                                    {card.label}
                                </div>
                                {card.value ? (
                                    <div style={{ fontSize: 28, fontWeight: 800, color: card.valueColor, lineHeight: 1 }}>
                                        {card.value}
                                    </div>
                                ) : (
                                    <div style={{
                                        display: "inline-block",
                                        background: card.badgeColor.bg,
                                        color: card.badgeColor.text,
                                        fontWeight: 700,
                                        fontSize: 14,
                                        borderRadius: 8,
                                        padding: "4px 14px",
                                    }}>
                                        {card.badge}
                                    </div>
                                )}
                                <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 5 }}>{card.sub}</div>
                            </div>
                        );
                    })}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                    <span style={{ fontSize: 13, color: "#64748b", marginRight: 4 }}>Zoom:</span>
                    {[["30", "30 days"], ["60", "60 days"], ["all", "All"]].map(function renderZoom(entry) {
                        const key = entry[0];
                        const label = entry[1];
                        return (
                            <button
                                key={key}
                                onClick={function () { setZoom(key); }}
                                style={{
                                    padding: "5px 16px",
                                    borderRadius: 8,
                                    border: zoom === key ? "1.5px solid #2563eb" : "1.5px solid #e2e8f0",
                                    background: zoom === key ? "#eff6ff" : "#fff",
                                    color: zoom === key ? "#2563eb" : "#475569",
                                    fontWeight: zoom === key ? 700 : 500,
                                    fontSize: 13,
                                    cursor: "pointer",
                                    transition: "all 0.15s",
                                }}
                                type="button"
                            >
                                {label}
                            </button>
                        );
                    })}
                </div>

                <div style={{ position: "relative", background: "#fff", borderRadius: 14, overflow: "hidden" }}>
                    <ResponsiveContainer width="100%" height={300}>
                        <RechartsLineChart data={historyData} margin={{ top: 16, right: 18, left: 8, bottom: 0 }}>
                            {historyScale.showThresholdInChart ? (
                                <RechartsReferenceArea y1={95} y2={historyDomain[1]} fill="rgba(134,239,172,0.15)" ifOverflow="extendDomain" />
                            ) : null}
                            <RechartsReferenceArea
                                y1={historyDomain[0]}
                                y2={historyScale.showThresholdInChart ? 95 : historyDomain[1]}
                                fill="rgba(252,165,165,0.18)"
                                ifOverflow="extendDomain"
                            />
                            <RechartsCartesianGrid stroke="#e5edf8" vertical={false} />
                            <RechartsXAxis
                                dataKey="timestamp"
                                type="number"
                                domain={["dataMin", "dataMax"]}
                                ticks={historyTicks}
                                tickFormatter={formatDateLabel}
                                tick={{ fontSize: 12, fill: "#475569", fontWeight: 700 }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <RechartsYAxis
                                domain={historyDomain}
                                tickFormatter={function (value) { return value + "%"; }}
                                tick={{ fontSize: 12, fill: "#475569", fontWeight: 700 }}
                                axisLine={false}
                                tickLine={false}
                                width={52}
                                ticks={historyTicksY}
                            />
                            <RechartsTooltip content={<HistoryTooltip />} />
                            {historyScale.showThresholdInChart ? (
                                <RechartsReferenceLine y={95} stroke="#f87171" strokeDasharray="6 3" strokeWidth={1.5} />
                            ) : null}
                            <RechartsLine
                                type="monotone"
                                dataKey="soh"
                                stroke="#2563eb"
                                strokeWidth={2.2}
                                dot={renderHistoryDot}
                                activeDot={{ r: 5, fill: "#2563eb", stroke: "#fff", strokeWidth: 2 }}
                                isAnimationActive={false}
                                connectNulls={false}
                            />
                        </RechartsLineChart>
                    </ResponsiveContainer>
                </div>

                <div style={{ textAlign: "center", color: "#64748b", fontSize: 12.5, marginTop: 8, fontWeight: 700 }}>Time</div>
            </section>

            <section className="panel soh-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4, gap: 18, flexWrap: "wrap" }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: 26, fontWeight: 800, color: "#0f172a", letterSpacing: -0.5 }}>24-Month Forecast</h2>
                        <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13.5 }}>
                            Projected SOH trend with an adaptive scale for normal and critical battery states.
                        </p>
                    </div>
                    <div style={{ display: "flex", gap: 20, alignItems: "center", fontSize: 12.5, color: "#475569", flexWrap: "wrap" }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#16a34a", display: "inline-block" }} />
                            Current SOH
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ width: 24, height: 0, borderTop: "2.5px dashed #f59e0b", display: "inline-block" }} />
                            Projected SOH
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ width: 24, height: 0, borderTop: "2.5px dashed #ef4444", display: "inline-block" }} />
                            Warning threshold
                        </span>
                    </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 14, margin: "22px 0 24px" }}>
                    {[
                        {
                            label: "CURRENT SOH",
                            value: currentSOH !== null ? currentSOH.toFixed(1) + "%" : "--",
                            sub: historyData.length ? formatDateLabel(historyData[historyData.length - 1].timestamp) : "No data",
                        },
                        {
                            label: "24-MONTH ESTIMATE",
                            value: forecastEnd !== null ? forecastEnd.toFixed(1) + "%" : "--",
                            sub: forecastEndPoint ? formatDateLabel(forecastEndPoint.timestamp) : "No forecast",
                            valueColor: "#d97706",
                        },
                        {
                            label: "LOWEST FORECAST",
                            value: forecastMin !== null ? forecastMin.toFixed(1) + "%" : "--",
                            sub: forecastLowestPoint ? formatDateLabel(forecastLowestPoint.timestamp) : "Across projection window",
                            valueColor: "#d97706",
                        },
                        {
                            label: "STATUS",
                            badge: forecastStatus === "Stable" ? "Healthy" : "Warning",
                            badgeColor: forecastStatus === "Stable"
                                ? { bg: "#dcfce7", text: "#16a34a", border: "1px solid #bbf7d0" }
                                : { bg: "#fee2e2", text: "#dc2626", border: "1px solid #fecaca" },
                            sub: forecastStatus === "Stable" ? "Forecast remains above the warning threshold." : "Forecast remains below the warning threshold.",
                        },
                    ].map(function renderForecastCard(card, index) {
                        return (
                            <div key={index} style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: "16px 18px", background: "#fff" }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", letterSpacing: 0.8, marginBottom: 6 }}>
                                    {card.label}
                                </div>
                                {card.value ? (
                                    <div style={{ fontSize: 28, fontWeight: 800, color: card.valueColor || "#0f172a", lineHeight: 1 }}>
                                        {card.value}
                                    </div>
                                ) : (
                                    <div style={{
                                        display: "inline-block",
                                        background: card.badgeColor.bg,
                                        color: card.badgeColor.text,
                                        border: card.badgeColor.border,
                                        fontWeight: 700,
                                        fontSize: 14,
                                        borderRadius: 8,
                                        padding: "4px 14px",
                                    }}>
                                        {card.badge}
                                    </div>
                                )}
                                <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 5 }}>{card.sub}</div>
                            </div>
                        );
                    })}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 10, color: "#64748b", fontSize: 13 }}>
                    <span style={{
                        width: 18,
                        height: 18,
                        borderRadius: "50%",
                        border: "1.5px solid #94a3b8",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#64748b",
                        flexShrink: 0,
                    }}>i</span>
                    {forecastScale.criticalRange
                        ? "Critical-range forecast view is enabled so very low SOH values remain readable. The 80% threshold is shown in the legend and status summary."
                        : "The forecast shows the expected SOH trend over the next 24 months using the latest battery history."}
                </div>

                <div style={{ position: "relative", background: "#fff", borderRadius: 14, overflow: "hidden" }}>
                    <ResponsiveContainer width="100%" height={320}>
                        <RechartsLineChart data={forecastData} margin={{ top: 18, right: 32, left: 8, bottom: 0 }}>
                            {forecastScale.showThresholdInChart ? (
                                <RechartsReferenceArea y1={80} y2={forecastDomain[1]} fill="rgba(134,239,172,0.13)" ifOverflow="extendDomain" />
                            ) : null}
                            <RechartsReferenceArea
                                y1={forecastDomain[0]}
                                y2={forecastScale.showThresholdInChart ? 80 : forecastDomain[1]}
                                fill="rgba(252,165,165,0.13)"
                                ifOverflow="extendDomain"
                            />
                            <RechartsCartesianGrid stroke="#e5edf8" vertical={false} />
                            <RechartsXAxis
                                dataKey="timestamp"
                                type="number"
                                domain={["dataMin", "dataMax"]}
                                ticks={forecastTicks}
                                tick={function renderForecastTick(props) {
                                    const point = forecastData.find(function (item) { return item.timestamp === props.payload.value; });
                                    return (
                                        <g transform={"translate(" + props.x + "," + props.y + ")"}>
                                            <text x={0} y={0} dy={14} textAnchor="middle" fontSize={11.5} fill={point && point.isStart ? "#16a34a" : "#475569"} fontWeight={700}>
                                                {point ? point.label : ""}
                                            </text>
                                            {point && point.sublabel ? (
                                                <text x={0} y={0} dy={28} textAnchor="middle" fontSize={10.5} fill={point.isStart ? "#16a34a" : "#94a3b8"} fontWeight={point.isStart ? 700 : 500}>
                                                    {point.sublabel}
                                                </text>
                                            ) : null}
                                        </g>
                                    );
                                }}
                                axisLine={false}
                                tickLine={false}
                                height={54}
                            />
                            <RechartsYAxis
                                domain={forecastDomain}
                                tickFormatter={function (value) { return value + "%"; }}
                                tick={{ fontSize: 12, fill: "#475569", fontWeight: 700 }}
                                axisLine={false}
                                tickLine={false}
                                width={52}
                                ticks={forecastTicksY}
                            />
                            <RechartsTooltip content={<ForecastTooltip />} />
                            {forecastScale.showThresholdInChart ? (
                                <RechartsReferenceLine
                                    y={80}
                                    stroke="#ef4444"
                                    strokeDasharray="7 4"
                                    strokeWidth={1.8}
                                    label={{
                                        value: "80%",
                                        position: "right",
                                        fontSize: 12,
                                        fill: "#ef4444",
                                        fontWeight: 700,
                                        dx: 6,
                                    }}
                                />
                            ) : null}
                            <RechartsLine
                                type="monotone"
                                dataKey="current"
                                stroke="#16a34a"
                                strokeWidth={0}
                                dot={function renderCurrentDot(props) {
                                    if (props.payload && props.payload.current !== null) {
                                        return <circle cx={props.cx} cy={props.cy} r={6} fill="#16a34a" stroke="#fff" strokeWidth={2} />;
                                    }
                                    return <g />;
                                }}
                                activeDot={{ r: 6, fill: "#16a34a", stroke: "#fff", strokeWidth: 2 }}
                                isAnimationActive={false}
                                connectNulls={false}
                            />
                            <RechartsLine
                                type="monotone"
                                dataKey="projected"
                                stroke="#f59e0b"
                                strokeWidth={2.2}
                                strokeDasharray="7 4"
                                dot={function renderProjectedDot(props) {
                                    if (props.payload && props.payload.isEnd) {
                                        return <circle cx={props.cx} cy={props.cy} r={6} fill="#f59e0b" stroke="#fff" strokeWidth={2} />;
                                    }
                                    return <g />;
                                }}
                                activeDot={{ r: 5, fill: "#f59e0b", stroke: "#fff", strokeWidth: 2 }}
                                isAnimationActive={false}
                                connectNulls={false}
                            />
                        </RechartsLineChart>
                    </ResponsiveContainer>
                </div>

                <div style={{ textAlign: "center", color: "#64748b", fontSize: 12.5, marginTop: 8, marginBottom: 16, fontWeight: 700 }}>Time</div>

                <div style={{
                    display: "flex",
                    gap: 40,
                    padding: "16px 20px",
                    border: "1px solid #f1f5f9",
                    borderRadius: 12,
                    background: "#f8fafc",
                    flexWrap: "wrap",
                }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                        <span style={{ marginTop: 3, width: 12, height: 12, borderRadius: "50%", border: "2px solid #16a34a", display: "inline-block", flexShrink: 0 }} />
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 13, color: "#0f172a" }}>Current SOH</div>
                            <div style={{ fontSize: 12, color: "#64748b" }}>The SOH measured on the latest available date.</div>
                        </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                        <span style={{ marginTop: 8, width: 22, height: 0, borderTop: "2.5px dashed #f59e0b", display: "inline-block", flexShrink: 0 }} />
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 13, color: "#0f172a" }}>Projected SOH</div>
                            <div style={{ fontSize: 12, color: "#64748b" }}>The forecasted SOH trend over the next 24 months.</div>
                        </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                        <span style={{ marginTop: 8, width: 22, height: 0, borderTop: "2.5px dashed #ef4444", display: "inline-block", flexShrink: 0 }} />
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 13, color: "#0f172a" }}>Warning threshold (80%)</div>
                            <div style={{ fontSize: 12, color: "#64748b" }}>SOH below this level may impact battery performance and reliability.</div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}

function CellGrid({ cells }) {
    const safeCells = Array.isArray(cells) ? cells : [];

    function heatmapStyle(cell) {
        if (cell.is_faulty) {
            return {
                background: "linear-gradient(135deg, rgba(254, 242, 242, 0.98), rgba(254, 202, 202, 0.56))",
                borderColor: "rgba(220, 38, 38, 0.32)",
            };
        }

        const voltageRatio = Math.max(0, Math.min(1, (Number(cell.voltage) - 3.0) / 1.2));
        const temperatureRatio = Math.max(0, Math.min(1, (Number(cell.temperature) - 20) / 20));
        const cool = 0.08 + voltageRatio * 0.22;
        const warm = 0.05 + temperatureRatio * 0.18;

        return {
            background: "linear-gradient(135deg, rgba(59, 130, 246, " + cool + "), rgba(16, 185, 129, " + warm + "))",
            borderColor: "rgba(59, 130, 246, " + (0.14 + voltageRatio * 0.24) + ")",
        };
    }

    return (
        <section className="panel">
            <div className="panel-header">
                <h2>Cell Detail</h2>
                <span>{safeCells.length} cells</span>
            </div>
            <div className="cell-grid">
                {safeCells.map(function renderCell(cell) {
                    return (
                        <div
                            className={"cell-card heatmap-card" + (cell.is_faulty ? " is-faulty" : "")}
                            key={cell.id}
                            style={heatmapStyle(cell)}
                        >
                            <strong>Cell {cell.id}</strong>
                            <div className="cell-voltage">{formatMetric(cell.voltage, "V", 3)}</div>
                            <span>{formatMetric(cell.temperature, "°C", 1)}</span>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

function DashboardView({ onDelete, selected, liveData, onRefresh }) {
    if (!selected) {
        return (
            <section className="panel empty-panel">
                <h2>No battery selected</h2>
                <p>Select a preset or custom battery to load the dashboard.</p>
            </section>
        );
    }

    const summary = liveData && liveData.pack_summary ? liveData.pack_summary : null;
    const metrics = liveData && liveData.model_performance ? liveData.model_performance : { mae: "--", r2_score: "--" };
    const alertText = summary && summary.alert !== "None" ? summary.alert : "Healthy";
    const safeLiveData = liveData || { cells: [], long_term_forecast: { history: [], projection: [], text: "--" } };

    return (
        <div className="dashboard-stack">
            <header className="topbar">
                <div>
                    <h1>IntelliBMS Battery Monitor</h1>
                    <p className="topbar-subtitle">{selected.name} / {selected.battery_type} / {alertText}</p>
                </div>
                <div className="topbar-actions">
                    <button className="toolbar-button primary" onClick={onRefresh} type="button">
                        Refresh Now
                    </button>
                    {selected.source === "custom" ? (
                        <button className="toolbar-button danger" onClick={function () { onDelete(selected.id); }} type="button">
                            Delete Battery
                        </button>
                    ) : null}
                </div>
            </header>

            <div className="metric-grid">
                <MetricCard tone="blue" label="Total Voltage" value={summary ? formatMetric(summary.total_voltage, "V", 2) : "--"} />
                <MetricCard tone="amber" label="Average Temperature" value={summary ? formatMetric(summary.avg_temperature, "°C", 1) : "--"} />
                <MetricCard tone="green" label="State of Health" value={summary ? formatMetric(summary.state_of_health, "%", 1) : "--"} />
                <MetricCard tone="violet" label="Model Accuracy" value={"MAE " + metrics.mae + " / R² " + metrics.r2_score} />
            </div>

            <MonitoringCharts liveData={safeLiveData} />
            <CellGrid cells={safeLiveData.cells} />
        </div>
    );
}

function Workspace({
    activeSection,
    catalog,
    error,
    form,
    liveData,
    message,
    onChange,
    onDelete,
    onRefresh,
    onSectionChange,
    onSelect,
    onSubmit,
    onUpload,
    selected,
    submitting,
    uploading,
}) {
    const sectionNotice = error || message;

    return (
        <main className="workspace">
            {activeSection === "dashboard" ? <DashboardView liveData={liveData} onDelete={onDelete} onRefresh={onRefresh} selected={selected} /> : null}
            {activeSection === "preset" ? (
                <BatteryGrid
                    items={catalog.predefined}
                    onSelect={function (item) {
                        onSelect(item);
                        onSectionChange("dashboard");
                    }}
                    selected={selected}
                    title="Preset Batteries"
                />
            ) : null}
            {activeSection === "custom" ? (
                <BatteryGrid
                    items={catalog.custom}
                    onDelete={onDelete}
                    onSelect={function (item) {
                        onSelect(item);
                        onSectionChange("dashboard");
                    }}
                    selected={selected}
                    title="Custom Batteries"
                />
            ) : null}
            {activeSection === "add" ? <BatteryForm form={form} notice={sectionNotice} onChange={onChange} onSubmit={onSubmit} submitting={submitting} /> : null}
            {activeSection === "import" ? <UploadPanel notice={sectionNotice} onUpload={onUpload} uploading={uploading} /> : null}
        </main>
    );
}

function IntelliBMSApp() {
    const [activeSection, setActiveSection] = useState("dashboard");
    const [catalog, setCatalog] = useState({ predefined: [], custom: [] });
    const [selected, setSelected] = useState(null);
    const [liveData, setLiveData] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");
    const [form, setForm] = useState(DEFAULT_FORM);
    const [pendingDeleteId, setPendingDeleteId] = useState(null);

    function changeSection(section) {
        setMessage("");
        setError("");
        setActiveSection(section);
    }

    async function loadCatalog(preferred) {
        try {
            const payload = await window.IntelliBMSApi.getBatteryCatalog();
            startTransition(function () {
                setCatalog(payload);
                setSelected(function (previous) {
                    return selectPreferredBattery(payload, preferred || previous);
                });
            });
        } catch (requestError) {
            setError(requestError.message);
        }
    }

    async function loadLiveData(selection) {
        if (!selection) {
            return;
        }

        try {
            const payload = await window.IntelliBMSApi.getLiveData(selection);
            startTransition(function () {
                setLiveData(payload);
            });
        } catch (requestError) {
            setError(requestError.message);
        }
    }

    useEffect(function () {
        loadCatalog();
    }, []);

    useEffect(function () {
        if (!selected) {
            setLiveData(null);
            return;
        }

        loadLiveData(selected);
        const intervalId = window.setInterval(function () {
            loadLiveData(selected);
        }, 3000);

        return function () {
            window.clearInterval(intervalId);
        };
    }, [selectionKey(selected)]);

    function updateForm(field, value) {
        setForm(function (previous) {
            return { ...previous, [field]: value };
        });
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setSubmitting(true);
        setError("");
        setMessage("");

        try {
            const createdBattery = await window.IntelliBMSApi.createBattery(form);
            setForm(DEFAULT_FORM);
            setMessage("");
            await loadCatalog({ id: createdBattery.id, source: "custom" });
            changeSection("dashboard");
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSubmitting(false);
        }
    }

    async function handleUpload(files) {
        setUploading(true);
        setError("");
        setMessage("");

        try {
            const response = await window.IntelliBMSApi.uploadBatteryFiles(files);
            setMessage("");
            await loadCatalog({ id: response.battery_id, source: "custom" });
            changeSection("dashboard");
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setUploading(false);
        }
    }

    async function handleDelete(batteryId) {
        if (!batteryId) {
            return;
        }

        setError("");
        setMessage("");

        try {
            await window.IntelliBMSApi.deleteBattery(batteryId);
            setMessage("");
            setPendingDeleteId(null);
            await loadCatalog();
        } catch (requestError) {
            setError(requestError.message);
        }
    }

    return (
        <div className="app-shell">
            <Sidebar activeSection={activeSection} onSectionChange={changeSection} />
            <Workspace
                activeSection={activeSection}
                catalog={catalog}
                error={error}
                form={form}
                liveData={liveData}
                message={message}
                onChange={updateForm}
                onDelete={setPendingDeleteId}
                onRefresh={function () {
                    loadLiveData(selected);
                }}
                onSectionChange={changeSection}
                onSelect={setSelected}
                onSubmit={handleSubmit}
                onUpload={handleUpload}
                selected={selected}
                submitting={submitting}
                uploading={uploading}
            />
            <ConfirmDialog
                open={pendingDeleteId !== null}
                title="Delete this custom battery?"
                onCancel={function () {
                    setPendingDeleteId(null);
                }}
                onConfirm={function () {
                    handleDelete(pendingDeleteId);
                }}
            />
        </div>
    );
}

window.IntelliBMSApp = IntelliBMSApp;
