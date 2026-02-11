/**
 * Daily outreach summary (America/Los_Angeles)
 * Adds Raw Leads per-sender breakdown: Ethan, Advaith, Abhay (aka Abhay).
 */
function dailyOutreachReport() {
    // ----- CONFIG -----
    const SPREADSHEET_ID = "1pJbbD_o_duLKDTj_Nvtn0LDaEwuSCHK4o_9U4hRav74";
    const SHEETS = ["Macros", "Micros", "Submicros", "Theme Pages"];
    const SHEET_RAW = "Raw Leads";
    const TIMEZONE = "America/Los_Angeles";
    const WEBHOOK_URL = "https://hooks.slack.com/services/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";

    // ----- TODAY (Pacific) -----
    const now = new Date();
    const today = Utilities.formatDate(now, TIMEZONE, "yyyy-MM-dd"); // e.g., "2025-11-04"
    const labhayl = Utilities.formatDate(now, TIMEZONE, "MMM d");       // e.g., "Nov 4"

    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

    // ----- Raw Leads (supports headers like "Nov 4th, 2025 (Ethan)" or "Nov 4th (Abhay)") -----
    const rawVariants = getDateHeaderVariantsForToday(now, TIMEZONE); // {withYear, noYear, display}
    const rawCounts = countRawLeadsBySenderForToday(ss, SHEET_RAW, rawVariants);

    let totalDMs = 0;
    let totalFUs = 0;
    let summary = `<!channel>\n\n🧬 *REGEN App Outreach Summary (${labhayl})*\n\n`;

    // headers to detect
    const INITIAL_RE = /^initial\s*date$/i;
    const FU_DATE_RE = /^(?:f\/u|fu\b|follow[\s/_\-.]*up|followup).*?\bdate\b/i;
    const STATUS_RE = /\bstatus\b/i;

    // INCLUDED statuses for followups
    const INCLUDED_STATUSES = new Set(["followup sent"]);

    const allSheets = ss.getSheets();

    for (const targetName of SHEETS) {
        // Robust finding
        let sh = ss.getSheetByName(targetName);

        // Fuzzy fallback if exact match fails
        if (!sh) {
            const targetSimple = targetName.toLowerCase().replace(/\s/g, "");
            for (const s of allSheets) {
                const sName = s.getName();
                const sSimple = sName.toLowerCase().replace(/\s/g, "");
                if (sSimple === targetSimple) {
                    sh = s;
                    console.log(`[INFO] Fuzzy matched sheet "${targetName}" to "${sName}"`);
                    break;
                }
            }
        }

        if (!sh) {
            console.log(`[WARN] Sheet not found: "${targetName}"`);
            continue;
        }

        const name = sh.getName(); // use actual name found

        const lastRow = sh.getLastRow();
        const lastCol = sh.getLastColumn();
        if (lastRow < 2 || lastCol < 1) continue;

        const header = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(h => String(h || "").trim());
        const data = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();

        const idxInitial = header.findIndex(h => INITIAL_RE.test(h));
        const idxFUDate = header.findIndex(h => FU_DATE_RE.test(h));
        let idxStatus = header.findIndex(h => STATUS_RE.test(h));
        if (idxStatus < 0) idxStatus = -1; // optional

        console.log(`[DEBUG] Sheet "${name}": InitialCol=${idxInitial}, FUCol=${idxFUDate}, StatusCol=${idxStatus}, NumRows=${data.length}`);

        let dms = 0, fus = 0;

        for (let r = 0; r < data.length; r++) {
            const row = data[r];

            // DMs: Initial Date == today
            if (idxInitial >= 0) {
                const d = normalizeDate(row[idxInitial], TIMEZONE);
                if (d === today) dms++;
            }

            // Debug first few rows if count is low
            if (r < 3 && idxInitial >= 0) {
                // console.log(`[DEBUG] Row ${r} Val="${row[idxInitial]}" -> Norm="${normalizeDate(row[idxInitial], TIMEZONE)}" vs Today="${today}"`);
            }

            // Follow-ups: Followup Date == today AND status included
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
        summary += `• ${name}: ${dms} DMs, ${fus} follow-ups\n`;
    }

    // Raw Leads line (total + per-sender)
    const rl = rawCounts;
    const perLine =
        `Ethan ${rl.per.Ethan || 0}, Advaith ${rl.per.Advaith || 0}, Abhay ${rl.per.Abhay || 0}`;
    summary += `• Raw Leads (${rawVariants.display}): ${rl.total} (${perLine})\n`;

    // Totals
    summary += `\n*Total:* ${totalDMs} DMs, ${totalFUs} follow-ups`;
    Logger.log(summary);

    // ----- Slack -----
    UrlFetchApp.fetch(WEBHOOK_URL, {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify({ text: summary }),
        muteHttpExceptions: true,
    });

    // ===== Helpers =====
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
            // If year is missing, we assume CURRENT YEAR? Or check if it parses defaults.
            // Date.parse often requires a year for correct logic or defaults to current/1900.
            // Let's rely on Date.parse but append year if missing?
            // Actually standardizing on Date.parse is risky for partial dates. 
            // Let's append current year if it looks like "Nov 4" or "Nov 4th".

            // Remove ordinal suffixes strictly for parsing if needed, though Date.parse usually fails on "4th"
            s = s.replace(/(\d+)(st|nd|rd|th)/i, "$1");

            const t = Date.parse(s);
            if (!isNaN(t)) return Utilities.formatDate(new Date(t), tz, "yyyy-MM-dd");

            // If failed, maybe it's "Nov 4" without year.
            // Append year?
            const nowYear = new Date().getFullYear(); // Use system time or passed in? 
            // The function doesn't have reference to 'now' year context easily unless derived from tz.
            // Let's try appending the year from the script config if available, but here we just try adding current year.
            const t2 = Date.parse(`${s} ${nowYear}`);
            if (!isNaN(t2)) return Utilities.formatDate(new Date(t2), tz, "yyyy-MM-dd");
        }
        return null;
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

    function ordinal(n) {
        const j = n % 10, k = n % 100;
        if (j === 1 && k !== 11) return "st";
        if (j === 2 && k !== 12) return "nd";
        if (j === 3 && k !== 13) return "rd";
        return "th";
    }

    /**
     * Counts Raw Leads for today's date across columns like:
     *  - "Nov 4th, 2025 (Ethan)"
     *  - "Nov 4th (Abhay)"
     *  - "Nov 4th, 2025"
     * Returns { total, per: { Ethan, Advaith, Abhay } }.
     */
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

        // Canonicalize sender names (Abhay→Abhay)
        const canon = (raw) => {
            const s = String(raw || "").trim().toLowerCase();
            if (!s) return null;
            if (s === "abhay" || s === "abhay") return "Abhay";
            if (s === "ethan") return "Ethan";
            if (s === "advaith") return "Advaith";
            return null;
        };

        // Find all matching columns
        const matchCols = [];
        headers.forEach((h, idx) => {
            const m = h.match(re);
            if (m) {
                const sender = canon(m[1]);
                matchCols.push({ colIdx: idx + 1, sender });
            }
        });

        if (matchCols.length === 0) {
            return { total: 0, per: { Ethan: 0, Advaith: 0, Abhay: 0 } };
        }

        const numRows = Math.max(0, lastRow - 1);
        const totalStruct = { total: 0, per: { Ethan: 0, Advaith: 0, Abhay: 0 } };
        if (numRows === 0) return totalStruct;

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
}
