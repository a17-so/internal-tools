
// Mock Google Apps Script environment
const Logger = {
    log: (...args) => console.log(...args)
};

const Utilities = {
    formatDate: (date, tz, format) => {
        const d = new Date(date);
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        if (format === "yyyy-MM-dd") {
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }
        return d.toISOString();
    }
};

const UrlFetchApp = {
    fetch: (url, params) => {
        console.log(`[Mock Fetch] POST to ${url}`);
    }
};

// Mock Spreadsheet Data
class MockRange {
    constructor(values) {
        this.values = values;
    }
    getValues() {
        return this.values;
    }
}

class MockSheet {
    constructor(name, data) {
        this.name = name;
        this.data = data; // 2D array
    }
    getLastRow() {
        return this.data.length;
    }
    getLastColumn() {
        return this.data[0] ? this.data[0].length : 0;
    }
    getRange(row, col, numRows, numCols) {
        const rStart = row - 1;
        const cStart = col - 1;
        const rEnd = rStart + numRows;
        const cEnd = cStart + numCols;
        const slice = this.data.slice(rStart, rEnd).map(row => row.slice(cStart, cEnd));
        return new MockRange(slice);
    }
    getName() { return this.name; }
}

class MockSpreadsheet {
    constructor(sheets) {
        this.sheets = sheets;
    }
    getSheetByName(name) {
        return this.sheets.find(s => s.name === name) || null;
    }
}

// Minimal logic from main.js needing test
function normalizeDate(v, tz) {
    // simplified for test
    if (v === "2025-11-04") return "2025-11-04";
    if (v instanceof Date) return Utilities.formatDate(v, tz, "yyyy-MM-dd");
    return null;
}

function runTest() {
    const TIMEZONE = "America/Los_Angeles";
    const today = "2025-11-04"; // hardcoded for test

    // Mock Sheets
    const mockSheets = [
        new MockSheet("Macros", [
            ["Initial Date", "Followup Date", "Status"],
            ["2025-11-04", "", ""]
        ]),
        new MockSheet("Sub Micros", [
            ["Initial Date", "Followup Date", "Status"],
            ["2025-11-04", "", ""],
            ["2025-11-04", "2025-11-04", "followup sent"]
        ])
    ];

    const ss = new MockSpreadsheet(mockSheets);

    const SHEETS = ["Macros", "Micros", "Submicros", "Theme Pages"];
    const INITIAL_RE = /^initial\s*date$/i;

    console.log("Checking SHEETS:", SHEETS);

    const allSheets = ss.sheets; // Use the mock property directly or add getSheets() 

    for (const targetName of SHEETS) {
        // Robust finding
        let sh = null;

        // 1. Try exact match first
        sh = ss.getSheetByName(targetName);

        // 2. If not found, try fuzzy match
        if (!sh) {
            const targetSimple = targetName.toLowerCase().replace(/\s/g, "");
            // In real script: ss.getSheets()
            // In mock: ss.sheets
            const candidates = ss.sheets;
            for (const s of candidates) {
                const sName = s.getName();
                const sSimple = sName.toLowerCase().replace(/\s/g, "");
                if (sSimple === targetSimple) {
                    sh = s;
                    console.log(`[INFO] Fuzzy match: "${targetName}" -> "${sName}"`);
                    break;
                }
            }
        }

        if (!sh) {
            console.log(`[WARNING] Sheet not found: "${targetName}"`);
            continue;
        }

        const name = sh.getName();

        const lastRow = sh.getLastRow();
        const lastCol = sh.getLastColumn();
        const header = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(h => String(h || "").trim());
        const data = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();

        const idxInitial = header.findIndex(h => INITIAL_RE.test(h));

        let dms = 0;
        for (let r = 0; r < data.length; r++) {
            const row = data[r];
            if (idxInitial >= 0) {
                // Simplified matching
                if (row[idxInitial] === today) dms++;
            }
        }
        console.log(`Sheet "${name}" found. DMs: ${dms}`);
    }
}

runTest();
