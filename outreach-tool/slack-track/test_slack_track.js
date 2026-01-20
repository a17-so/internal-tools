
// Mock Google Apps Script environment
const Logger = {
    log: (...args) => console.log(...args)
};

const Utilities = {
    formatDate: (date, tz, format) => {
        // Very basic mock implementation for the formats used in the script
        // Note: ignoring timezone for local test simplicity unless crucial, 
        // assuming local run is sufficient for logic testing.
        const d = new Date(date);
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        if (format === "yyyy-MM-dd") {
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }
        if (format === "MMM d") {
            return `${months[d.getMonth()]} ${d.getDate()}`;
        }
        if (format === "MMM") {
            return months[d.getMonth()];
        }
        if (format === "d") {
            return String(d.getDate());
        }
        if (format === "yyyy") {
            return String(d.getFullYear());
        }
        return d.toISOString();
    }
};

const UrlFetchApp = {
    fetch: (url, params) => {
        console.log(`[Mock Fetch] POST to ${url}`);
        console.log(`Payload: ${params.payload}`);
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
        // 1-based index to 0-based
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

const SpreadsheetApp = {
    openById: (id) => {
        return new MockSpreadsheet(mockSheets);
    }
};

// --- INSERT MAIN.JS LOGIC HERE FOR TESTING (We will copy-paste the functions we want to test or require them if we structure it right, but for this task I'll inline the logic to be tested by pasting the original code below) ---

// For the test, I'll copy the logic from main.js effectively, but I need to make sure I can call it.
// Since main.js is a GAS script, it's global scope. I'll paste the relevant functions here.

// -----------------------------------------------------------------------------
// PASTE START: Functions from main.js (slightly adapted to remove outer function if needed or just called)
// -----------------------------------------------------------------------------

// We'll reimplement the core logic pieces here or wrap them to test what's broken.
// Specifically we want to test `normalizeDate` and the main report generation logic.

// Let's bring in the HELPER functions from main.js first as they are crucial for the failure.

function normalizeDate(v, tz) {
    if (v instanceof Date && !isNaN(v)) return Utilities.formatDate(v, tz, "yyyy-MM-dd");
    if (typeof v === "number" && !isNaN(v)) {
        const millis = Math.round((v - 25569) * 86400 * 1000); // Excel serial → ms
        return Utilities.formatDate(new Date(millis), tz, "yyyy-MM-dd");
    }
    if (typeof v === "string") {
        let s = v.trim();
        if (!s) return null;

        // 1. Try ISO-ish YYYY-MM-DD
        let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
        if (m) {
            return `${m[1]}-${String(m[2]).padStart(2, "0")}-${String(m[3]).padStart(2, "0")}`;
        }

        // 2. Try MM/DD/YYYY or M/D/YY
        m = s.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})/);
        if (m) {
            let y = parseInt(m[3], 10);
            if (y < 100) y += 2000; // assumption for 2-digit year
            return `${y}-${String(m[1]).padStart(2, "0")}-${String(m[2]).padStart(2, "0")}`;
        }

        // 3. Try "MMM d, yyyy" or "MMM d" or "Nov 4th" details
        s = s.replace(/(\d+)(st|nd|rd|th)/i, "$1");

        const t = Date.parse(s);
        if (!isNaN(t)) return Utilities.formatDate(new Date(t), tz, "yyyy-MM-dd");

        // If failed, maybe it's "Nov 4" without year.
        const nowYear = new Date().getFullYear();
        const t2 = Date.parse(`${s} ${nowYear}`);
        if (!isNaN(t2)) return Utilities.formatDate(new Date(t2), tz, "yyyy-MM-dd");
    }
    return null;
}

function ordinal(n) {
    const j = n % 10, k = n % 100;
    if (j === 1 && k !== 11) return "st";
    if (j === 2 && k !== 12) return "nd";
    if (j === 3 && k !== 13) return "rd";
    return "th";
}

function getDateHeaderVariantsForToday(dateObj, tz) {
    const mon = Utilities.formatDate(dateObj, tz, "MMM");       // "Nov"
    const day = parseInt(Utilities.formatDate(dateObj, tz, "d"), 10); // 1..31
    const yr = Utilities.formatDate(dateObj, tz, "yyyy");      // "2025"
    const ord = ordinal(day);
    return {
        withYear: `${mon} ${day}${ord}, ${yr}`, // "Nov 4th, 2025"
        noYear: `${mon} ${day}${ord}`,        // "Nov 4th"
        display: `${mon} ${day}${ord}, ${yr}`,
        // helper components for fuzzy matching
        mon, day, yr, ord
    };
}

function countRawLeadsBySenderForToday(ss, sheetName, variants) {
    const sh = ss.getSheetByName(sheetName);
    if (!sh) return { total: 0, per: { Ethan: 0, Advaith: 0, Abhay: 0 } };

    const lastRow = sh.getLastRow();
    const lastCol = sh.getLastColumn();
    // if (lastCol < 1) return { total: 0, per: { Ethan: 0, Advaith: 0, Abhay: 0 } }; // commented out to save lines or handled implicitly

    const headers = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(h => String(h || "").trim());

    // Flexible regex construction
    // We want to match: Month matches, Day matches (with or without ordinal), Year matches (optional), Comma (optional)
    const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

    // Construct regex parts
    const monPart = esc(variants.mon);
    const dayPart = `0?${variants.day}(?:${variants.ord})?`; // e.g. "4" or "04" or "4th"
    const yearPart = `(?:,?\\s*${variants.yr})?`; // ", 2025" or " 2025" or ""

    // Full date pattern: ^Nov\s+4(?:th)?(?:,?\s*2025)?
    const datePattern = `${monPart}\\s+${dayPart}${yearPart}`;

    const re = new RegExp(
        `^${datePattern}(?:\\s*\\(([^)]+)\\))?\\s*$`,
        "i"
    );

    // Log for debugging
    console.log(`[DEBUG] Raw Leads Regex: ${re}`);

    // Canonicalize sender names (Abhay→Abhay)
    const canon = (raw) => {
        const s = String(raw || "").trim().toLowerCase();
        if (!s) return null;
        if (s === "abhay" || s === "abhay") return "Abhay";
        if (s === "ethan") return "Ethan";
        if (s === "advaith") return "Advaith";
        return null; // ignore unknown senders in per breakdown (but still counted in total)
    };

    // Find all matching columns for today's date (possibly multiple sender-specific columns)
    const matchCols = [];
    headers.forEach((h, idx) => {
        const m = h.match(re);
        if (m) {
            const sender = canon(m[1]);
            matchCols.push({ colIdx: idx + 1, sender }); // 1-based for Range
            console.log(`[DEBUG] Matched Header: "${h}" -> Sender: ${sender}`);
        }
    });

    if (matchCols.length === 0) {
        return { total: 0, per: { Ethan: 0, Advaith: 0, Abhay: 0 } };
    }

    const numRows = Math.max(0, lastRow - 1);
    const totalStruct = { total: 0, per: { Ethan: 0, Advaith: 0, Abhay: 0 } };
    if (numRows === 0) return totalStruct;

    // Count non-empty cells in each matched column
    for (const { colIdx, sender } of matchCols) {
        const colValues = sh.getRange(2, colIdx, numRows, 1).getValues();
        let c = 0;
        for (let i = 0; i < colValues.length; i++) {
            const cell = colValues[i][0];
            if (cell !== null && String(cell).trim() !== "") c++;
        }
        totalStruct.total += c;
        if (sender && totalStruct.per.hasOwnProperty(sender)) totalStruct.per[sender] += c;
    }

    return totalStruct;
}

// Main logic wrapper for testing
function runDailyOutreachReportTest() {
    // Setup Mock Data
    const TIMEZONE = "America/Los_Angeles";

    // !!! SET THE DATE TO MATCH YOUR TEST DATA !!!
    // Let's pretend today is Nov 4th, 2025 to match the comments in file
    const now = new Date("2025-11-04T12:00:00");
    // Just overwrite Date constructor for the test or pass it in? 
    // Easier to just pass 'now' where needed or rely on variable.

    const today = Utilities.formatDate(now, TIMEZONE, "yyyy-MM-dd");

    console.log(`\n--- Running Test for Date: ${today} ---`);

    // Mock Sheets with tricky headers and date formats
    const mockSheets = [
        new MockSheet("Macros", [
            ["Initial Date", "Followup Date", "Status"],
            [new Date("2025-11-04"), "", ""], // Should count 1 DM
            ["11/04/2025", "2025-11-04", "followup sent"], // Should count 1 DM, 1 FU
            ["Nov 4, 2025", "Nov 4", "followup sent"], // Should count 1 DM, 1 FU (if parsing works)
            ["Some other date", "11/04/25", "followup sent"] // Should count 1 FU
        ]),
        new MockSheet("raw leads", [
            // Header variations that might be failing
            ["Nov 4th, 2025 (Ethan)", "Nov 4th (Abhay)", "Nov 4th 2025 (Advaith)", "Nov 4th, 2025"],
            ["link1", "link2", "link3", "link4"],
            ["link5", "", "link6", ""]
        ])
    ];

    // Wiring it up
    const ss = new MockSpreadsheet(mockSheets);

    // --- TEST RAW LEADS COUNT ---
    const rawVariants = getDateHeaderVariantsForToday(now, TIMEZONE);
    console.log("Raw Variants:", rawVariants);

    const rawCounts = countRawLeadsBySenderForToday(ss, "raw leads", rawVariants);
    console.log("Raw Counts Result:", JSON.stringify(rawCounts, null, 2));

    // --- TEST DM/FU COUNT ---
    // Copying logic from dailyOutreachReport loop briefly

    const SHEETS = ["Macros"];
    const INITIAL_RE = /^initial\s*date$/i;
    const FU_DATE_RE = /^(?:f\/u|fu\b|follow[\s/_\-.]*up|followup).*?\bdate\b/i;
    const STATUS_RE = /\bstatus\b/i;
    const INCLUDED_STATUSES = new Set(["followup sent"]);

    let totalDMs = 0;
    let totalFUs = 0;

    for (const name of SHEETS) {
        const sh = ss.getSheetByName(name);
        if (!sh) continue;

        const lastRow = sh.getLastRow();
        const lastCol = sh.getLastColumn();
        const header = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(h => String(h || "").trim());
        const data = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();

        const idxInitial = header.findIndex(h => INITIAL_RE.test(h));
        const idxFUDate = header.findIndex(h => FU_DATE_RE.test(h));
        let idxStatus = header.findIndex(h => STATUS_RE.test(h));

        let dms = 0, fus = 0;

        for (let r = 0; r < data.length; r++) {
            const row = data[r];

            // DMs
            if (idxInitial >= 0) {
                const d = normalizeDate(row[idxInitial], TIMEZONE);
                // console.log(`[DEBUG] Row ${r} Initial: "${row[idxInitial]}" -> parsed: ${d} vs today: ${today}`);
                if (d === today) dms++;
            }

            // FUs
            if (idxFUDate >= 0) {
                const fd = normalizeDate(row[idxFUDate], TIMEZONE);
                if (fd === today) {
                    const status = (idxStatus >= 0 ? String(row[idxStatus] || "").trim().toLowerCase() : "");
                    if (INCLUDED_STATUSES.has(status)) fus++;
                }
            }
        }
        totalDMs += dms;
        totalFUs += fus;
        console.log(`Sheet ${name}: DMs=${dms}, FUs=${fus}`);
    }

    console.log(`Global Totals: DMs=${totalDMs}, FUs=${totalFUs}`);
}

// Run it
runDailyOutreachReportTest();
